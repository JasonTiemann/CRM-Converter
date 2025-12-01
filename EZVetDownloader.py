from typing import *
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import json
import jsonpickle
from datetime import date, datetime
import time
import logging
import os
import traceback

# Local Imports
from AppointmentModel import AppointmentModel, DiagnosticResultModel, DiagnosticResultSpecificsModel, MedicationModel, TheraputicProcedureModel
from Utils import Utils


class EZVetDownloader:
    def __init__(self, settingsPath: str):
        # Initialize logger
        logging.basicConfig(filename='EZVetDownloader.log', level=logging.INFO)
        self.logger = logging.getLogger('EZVetDownloader')

        # Load settings to keep credentials out of code
        with open(settingsPath, 'r') as file:
            settings = json.load(file)
            self.user = settings['ezVet']['username']
            self.password = settings['ezVet']['password']
            self.url = settings['ezVet']['url']
            self.CurrentDate = datetime.strptime(settings['startDate'], "%Y-%m-%d").date()
            self.EndDate = datetime.strptime(settings['endDate'], "%Y-%m-%d").date()

            self.logger.info(f"""Loaded settings from {settingsPath}:
                User: {self.user}
                Password: {'*' * len(self.password)}
                URL: {self.url}
            """)

        # Initialize the web driver (will be passed to all classes)
        self.webDriver = webdriver.Chrome()
        self.webDriver.get(self.url)
        self.webDriver.maximize_window()
        self.awaiter = WebDriverWait(self.webDriver, 10)

        self.LogIn()

        # Init global variables 
        self.CurrentOwner = None
        self.CureentPatient = None
        self._cachedActiveTab = None
    
    def GetActiveTab(self):
        if self._cachedActiveTab is None or EC.staleness_of(self._cachedActiveTab):
            self._cachedActiveTab = self.webDriver.find_element(By.CSS_SELECTOR, "#rightpane > DIV.rtabdetails.active")
            
        return self._cachedActiveTab
            

    def __enter__(self):
        return self
    def __exit__(self, excType, excValue, traceback):
        if (excType is not None):
            self.logger.error(f"An exception occurred on date {self.CurrentDate} for Patient {self.CureentPatient} belonging to {self.CurrentOwner}: {excValue}\n{traceback}")
        else:
            # Close the web driver when done (leave open if error to allow debugging)
            self.webDriver.quit()
            self.logger.info("Closed web driver window successfully.")
        logging.shutdown()

    def LogIn(self):
        # Wait for page to load
        self.awaiter.until(
            lambda driver: driver.find_element(By.ID, "input-email") or driver.find_element(By.ID, "calendar")
        )

        if 'login.php' in self.webDriver.current_url:            
            usernameField = self.webDriver.find_element(By.ID, "input-email")
            passwordField = self.webDriver.find_element(By.ID, "input-password")
            loginButton = self.webDriver.find_element(By.ID, "div-login-button")

            usernameField.send_keys(self.user)
            passwordField.send_keys(self.password)
            loginButton.click()
            self.logger.info("ezVet login submitted.")
        else:
            self.logger.info("Already logged into ezVet")
            
            
    def CloseAllTabsButCalendar(self):
        self.awaiter.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#right > div.tabSliderHolder > div > div[role=tablist] > div.recordTab")))
        
        while True:
            closableTabs = self.webDriver.find_elements(By.CSS_SELECTOR, "#right > div.tabSliderHolder > div > div[role=tablist] > div.recordTab > button")
            if (len(closableTabs) == 0):
                break
            
            closableTabs[0].click()
            time.sleep(0.5)

    def GotoDay(self, toDate: date) -> bool:
        # Make sure we're on the dashboard
        self.CloseAllTabsButCalendar()
        
        # Wait for the mini calendar to load
        self.awaiter.until(EC.visibility_of_element_located((By.ID, "minical")))
        
        cal = None
        tries = 0
        while tries < 5:
            cal = self.GetActiveTab().find_element(By.ID, "minical")
            if cal is not None:
                break
            time.sleep(1)
            tries += 1
        if cal is None:
            raise Exception("Could not find ezVet mini calendar")
                
        
        

        # Make sure the correct month and year are present before selecting day
        yearSelector = Select(cal.find_element(By.CSS_SELECTOR, 'div > div:nth-child(1) > select:nth-child(4)'))
        yearSelector.select_by_visible_text(str(toDate.year))

        self.webDriver.implicitly_wait(1)  # Give time for the calendar to refresh

        monthSelector = Select(cal.find_element(By.CSS_SELECTOR, 'div > div:nth-child(1) > select:nth-child(2)'))
        monthSelector.select_by_visible_text(toDate.strftime("%B"))
        
        # Select the day
        tries = 0
        while tries < 5:
            shownDate = self.GetActiveTab().find_element(By.CSS_SELECTOR, "#currentdate > .current-day-active").text.strip().lower()
            expectedDate = toDate.strftime("%a, %d %b %Y").lower()
            if (shownDate == expectedDate):
                break
            for row in range(1, 6):
                for column in range(1, 8):
                    # Calendar gets rendered multiple times, so try a few times to get a non-stale element
                    attempts = 0
                    while attempts < 5:
                        try:
                            day = self.GetActiveTab().find_element(By.CSS_SELECTOR, f'#minical > div > div:nth-child(3) > div.minicalrow_new:nth-child({row}) > div:nth-child({column}) > a')
                            if Utils.TryParse(day.text, int) == toDate.day:
                                day.click()
                            break
                        except:
                            attempts += 1
                            time.sleep(0.5)
                    if tries >= 5:
                        raise Exception(f"Could not navigate to date {toDate} in ezVet after multiple tries")
            time.sleep(1)
            tries += 1
            
        if tries >= 5:
            return False
        
        return True
    

    def GetAppointments(self, getDate: date) -> List[AppointmentModel]:
        # Wait for the calendar to load
        self.awaiter.until(EC.visibility_of_element_located((By.ID, "calendar")))
        
        tries = 0
        while tries < 5:
            if not self.GotoDay(getDate):
                raise Exception(f"Could not navigate to date {getDate} in ezVet")
            time.sleep(3)
            if (self.GetActiveTab().find_element(By.CSS_SELECTOR, "#currentdate > .current-day-active").text.strip().lower() != getDate.strftime("%A, %d %B %Y").lower()):
                break
            tries += 1
        if tries >= 5:
            raise Exception(f"Could not navigate to date {getDate} in ezVet after multiple tries!")

        appointments: List[AppointmentModel] = []
        appointmentElements = self.GetActiveTab().find_elements(By.CSS_SELECTOR, "#calendarmain > .theGrid > div.appt.hasQtip.dblClickOpen")
        for appointmentElement in appointmentElements:
            hoverTries = 0
            while hoverTries < 5:
                try:
                    Utils.ScrollToPosition(self.webDriver, int(appointmentElement.value_of_css_property("top")[:-2]) - 100, id="calendarmain")
                    Utils.HoverOverElement(self.webDriver, appointmentElement)
                    self.awaiter.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#systemWrapper > div.qtip > div.qtip-content")))
                    break
                except:
                    hoverTries += 1
                    time.sleep(0.5)
                    if (hoverTries >= 5):
                        raise Exception(f"Could not hover over appointment on {getDate} with text '{appointmentElement.text}', skipping.")

            appointment = AppointmentModel()
            appointment.appointmentDate = getDate
            
            basicInfo = self.webDriver.find_elements(By.CSS_SELECTOR, "#systemWrapper > .qtip > .qtip-content > div:nth-child(1) > div > div > div.text")
            for info in basicInfo:
                title = info.find_element(By.CSS_SELECTOR, "label").text.strip().lower()
                value = info.find_element(By.CSS_SELECTOR, "span").text.strip()
                if "(" in value:
                    value = value[:value.index("(")].rstrip()

                if title == 'patient':
                    appointment.petName = value
                elif title == 'case owner':
                    appointment.doctor = value
                elif title == 'owner':
                    if ("," in value):
                        split = value.split(",")
                        value = f"{split[1].strip()} {split[0].strip()}"
                    appointment.clientName = value
                elif "reason" in title:
                    appointment.reason = value
                elif title == 'time':
                    appointment.appointmentTime = datetime.strptime(value, "%I:%M%p").time()
                elif title == 'date':
                    appointment.appointmentDate = datetime.strptime(value, "%m-%d-%Y").date()
                elif title == 'type':
                    appointment.type = value
                    
            appointment.cssPath = Utils.GetCssSelector(self.webDriver, appointmentElement)

            if appointment.HasBasicInfo():
                if 'ezyVet' in appointment.clientName or 'ezVet' in appointment.clientName or 'mctest' in appointment.clientName:
                    self.logger.warning(f"Skipping test appointment for {appointment.petName} with Dr. {appointment.doctor} on {appointment.appointmentDate} at {appointment.appointmentTime}")
                    continue
                appointments.append(appointment)
                self.logger.info(f"Found appointment for {appointment.petName} with Dr. {appointment.doctor} on {appointment.appointmentDate} at {appointment.appointmentTime}")
            else:
                self.logger.warning(f"Incomplete appointment found on {getDate} with text '{appointmentElement.text}', skipping.")
                
        return appointments


    def FillClinicalExamInfo(self, appointment: AppointmentModel) -> AppointmentModel:
        self.awaiter.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.animalMasterProblemList")))
        
        #Master Problems
        masterProblems = self.GetActiveTab().find_elements(By.CSS_SELECTOR, "div.medications > div > div > div.inputSection > div.inputSectionContent > div.animalMasterProblemList > table > tr")
        for row in masterProblems:
            columns = masterProblems.findElements(By.CSS_SELECTOR, "td")
            if (len(columns) <= 1):
                continue
            dateAndTime = columns[1].text.strip().split(" ")
            condition = columns[2].text.strip()
            parsedDate = datetime.strptime(dateAndTime[0], "%m-%d-%Y").date()
            parsedTime = datetime.strptime(dateAndTime[1], "%X%p").time()
            appointment.masterProblems.append((parsedDate, parsedTime, condition))
            
        # Health Status
        healthStatusTable = self.GetActiveTab().find_element(By.CSS_SELECTOR, "div.HealthStatus_subSectionContent > div:first-child > div.inputSection > div.inputSectionContent > div > table > tbody > tr:nth-child(1)")
        weightString = healthStatusTable.find_element(By.CSS_SELECTOR, "td:nth-child(2)").text.strip()
        appointment.weight = Utils.TryParse(weightString, float)
        hrText = healthStatusTable.find_element(By.CSS_SELECTOR, "td:nth-child(4)").text.strip()
        appointment.heartRate = Utils.TryParse(hrText, int)
        bcs = healthStatusTable.find_element(By.CSS_SELECTOR, "td:nth-child(6)").text.strip()
        if (bcs is not None and len(bcs) > 0):
            appointment.bodyConditionScore = Utils.TryParse(bcs[:bcs.index("/")] if bcs.index("/") > 0 else bcs, int)
        
        
        #History
        history = self.GetActiveTab().find_elements(By.CSS_SELECTOR, "div.VisitHistory_subSectionContent > div:first-child > div.inputSection > div.inputSectionContent > div > table > tbody > tr")
        historyText = ""
        for row in history:
            if len(historyText) > 0:
                historyText += "\n"
            historyText += f"{row.get_attribute('data-record-title')}"
        appointment.historyText = historyText
        
        #Physical Exam
        physExam = self.GetActiveTab().find_elements(By.CSS_SELECTOR, "div.VisitExam_subSectionContent > div:first-child > div.inputSection > div.inputSectionContent > div.VisitExamList > table > tbody > tr")
        physExamText = ""
        for row in physExam:
            if len(physExamText) > 0:
                physExamText += "\n"
            physExamText += f"{row.get_attribute('data-record-title')}"
        appointment.physicalExamText = physExamText
        
        #Assessment
        assessment = self.GetActiveTab().find_elements(By.CSS_SELECTOR, "div.ConsultAssessment_subSectionContent > div:first-child > div.inputSection > div.inputSectionContent > div.ConsultAssessmentList > table > tbody > tr")
        assessmentText = ""
        for row in assessment:
            if len(assessmentText) > 0:
                assessmentText += "\n"
            assessmentText += f"{row.get_attribute('data-record-title')}"
        appointment.assessmentText = assessmentText
        
        #Plan
        plan = self.GetActiveTab().find_elements(By.CSS_SELECTOR, "div.ConsultPlan_subSectionContent > div:first-child > div.inputSection > div.inputSectionContent > div.ConsultPlanList > table > tbody > tr")
        planText = ""
        for row in plan:
            if len(planText) > 0:
                planText += "\n"
            planText += f"{row.get_attribute('data-record-title')}"
        appointment.planText = planText
        
        return appointment
    
    
    def FillDiagnosticAndTreatmentInfo(self, appointment: AppointmentModel) -> AppointmentModel:
        self.awaiter.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.Medications_subSectionContent")))
        
        #Medications
        medications = self.GetActiveTab().find_elements(By.CSS_SELECTOR, "div.Medications_subSectionContent > div:first-child > div:first-child > div:first-child > div.inputSection > div.inputSectionContent > div.MedicationList > table > tbody > tr")
        for row in medications:
            columns = row.find_elements(By.CSS_SELECTOR, "td")
            
            dateAndTime = columns[0].text.strip().split(" ")
            parsedDate = datetime.strptime(dateAndTime[0], "%m-%d-%Y").date()
            parsedTime = datetime.strptime(dateAndTime[1], "%X%p").time()
            
            medication = MedicationModel()
            medication.date = parsedDate
            medication.time = parsedTime
            medication.name = columns[1].text.strip()
            medication.current = columns[2].find_element(By.CSS_SELECTOR, "input[type=checkbox]").get_attribute("checked") == "true"
            medication.instructions = columns[3].text.strip()
            medication.prescriber = columns[4].text.strip()
            medication.quantity = Utils.TryParse(columns[6].text.strip(), int)
            medication.daysSupply = Utils.TryParse(columns[9].text.strip(), int)
            medication.lastDispensed = datetime.strptime(columns[10].text.strip(), "%m-%d-%Y").date() if len(columns[10].text.strip()) > 2 else None
            appointment.medications.append(medication)
        
        #Theraputic Procedures
        theraputicProcedures = self.GetActiveTab().find_elements(By.CSS_SELECTOR, "div.Therapeutics_subSectionContent > div:first-child > div.inputSection > div.inputSectionContent > div.planTherapeuticsList > table > tbody > tr")
        for row in theraputicProcedures:
            columns = row.find_elements(By.CSS_SELECTOR, "td")
            dateAndTime = columns[0].text.strip().split(" ")
            parsedDate = datetime.strptime(dateAndTime[0], "%m-%d-%Y").date()
            parsedTime = datetime.strptime(dateAndTime[1], "%X%p").time()
            
            theraputicProcedure = TheraputicProcedureModel()
            
            theraputicProcedure.date = parsedDate
            theraputicProcedure.time = parsedTime
            theraputicProcedure.name = columns[1].text.strip()
            theraputicProcedure.specifics = columns[2].text.strip()
            if (len(theraputicProcedure.name) > 0):
                appointment.theraputicProcedures.append(theraputicProcedure)
            
        
        #Diagnostic Results
        diagnosticResults = self.GetActiveTab().find_elements(By.CSS_SELECTOR, "div.DiagnosticResults_subSectionContent > div:first-child > div.hasJaxRequest > div:nth-child(2) > div.inputSection > div.inputSectionContent > div.diagnosticResultsList > table > tbody > tr")
        diagnosticRow = 1
        for row in diagnosticResults:
            ActionChains(self.webDriver).double_click(row).perform()
            popupPath = "#systemWrapper > div > div.formbox > div.popup_content > form > div.popupFormInternal"
            
            try: # not all rows have a proper popup
                self.awaiter.until(EC.element_to_be_clickable((By.CSS_SELECTOR, popupPath)))
            except:
                self.logger.warn(f"Could not find diagnostic result popup for row {diagnosticRow} while getting diagnostic results for {appointment.petName} with Dr. {appointment.doctor} on {appointment.appointmentDate} at {appointment.appointmentTime}")
                continue
            
            popup = self.webDriver.find_element(By.CSS_SELECTOR, popupPath)
            diagnosticInfo = popup.find_element(By.CSS_SELECTOR, "table:first-of-type > tbody > tr:nth-child(1) ")
            basicInfoColumns = diagnosticInfo.find_elements(By.CSS_SELECTOR, "td")
            date = diagnosticInfo.find_element(By.CSS_SELECTOR, "div > div > inut.date").get_attribute("value")
            time = diagnosticInfo.find_element(By.CSS_SELECTOR, "div > div > input.time").get_attribute("value")
            results = diagnosticInfo.find_elements(By.CSS_SELECTOR, "table.diagnosticResult ? tbody > tr input:not([type=hidden])")
            
            diagnosticResult = DiagnosticResultModel()
            
            diagnosticResult.date = datetime.strptime(date, "%m-%d-%Y").date()
            diagnosticResult.time = datetime.strptime(time, "%X%p").time()
            diagnosticInfo.vetName = basicInfoColumns[3].text.strip()
            diagnosticResult.labReference = basicInfoColumns[4].text.strip()
            
            if ('radio' in diagnosticResult.labReference.lower()):
                popup.find_element(By.CSS_SELECTOR, "div.clickable[title=Attachments]").click()
                downloadModalPath = "div.formbox > div.formbox_inner > div.formbox_content > form[target=theMainFrame] > div.popupFormInternal"
                self.awaiter.until(EC.element_to_be_clickable((By.CSS_SELECTOR, downloadModalPath)))
                downloadModal = self.webDriver.find_element(By.CSS_SELECTOR, downloadModalPath)
                attachments = downloadModal.find_elements(By.CSS_SELECTOR, "ol > li > a")
                for attachment in attachments:
                    attachment.click()
                    test = 0
                    
                
            # Non-dental records
            else:
                for result in results:
                    columns = result.find_elements(By.CSS_SELECTOR, "td")
                    date = datetime.strptime(columns[0].get_attribute("value"), "%m-%d-%Y").date()
                    name = columns[1].get_attribute("value")
                    value = Utils.TryParse(columns[2].get_attribute("value"), float)
                    unit = columns[3].get_attribute("value")
                    low = Utils.TryParse(columns[4].get_attribute("value"), float)
                    high = Utils.TryParse(columns[5].get_attribute("value"), float)
                    qualifier = columns[6].get_attribute("value")
                    
                    diagnosticResult.results.append(DiagnosticResultSpecificsModel(date, name, value, unit, low, high, qualifier))
                
                resultNotes = diagnosticInfo.find_elements(By.CSS_SELECTOR, "textarea.DiagnosticResultNotes")
                
                
                diagnosticResult.outcomeText = resultNotes[0].text.strip()
                diagnosticResult.specifics = resultNotes[1].text.strip()
                
            appointment.diagnosticResults.append(diagnosticResult)
            
            popup.find_element(By.CSS_SELECTOR, "button.closeButton").click()
            diagnosticRow += 1
            
        
        # #Vaccinations
        # vaccinations = self.GetActiveTab().find_elements(By.CSS_SELECTOR, "div.Vaccination_subSectionContent > div:first-child > div.inputSection > div.inputSectionContent > div.VaccinationList > table > tbody > tr")
        # vaccinationsText = ""
        # for row in vaccinations:
        #     if len(vaccinationsText) > 0:
        #         vaccinationsText += "\n"
        #     vaccinationsText += f"{row.get_attribute('data-record-title')}"
        # appointment.vaccinations = vaccinationsText
        
        return appointment
        
    
        
    def FillAppointment(self, appointment: AppointmentModel) -> AppointmentModel:
        self.GotoDay(appointment.appointmentDate)
        
        self.awaiter.until(EC.visibility_of_element_located((By.CSS_SELECTOR, appointment.cssPath)))
        
        appointmentElement = self.GetActiveTab().find_element(By.CSS_SELECTOR, appointment.cssPath)
        ActionChains(self.webDriver).double_click(appointmentElement).perform()
        
        self.awaiter.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#rightpane > div.clinical > form > div.outerContent > .innerContent > div.detail > div.panels > div.subTab-details > div:first-child > div:first-child > div.sectionSelekta")))
        
        groupViewToggle = self.GetActiveTab().find_element(By.CSS_SELECTOR, "form > div.outerContent > .innerContent > div.detail > div.panels > div.subTab-details > div:first-child > div:first-child > div.sectionSelekta > div.selektaContainer > label.buttonHolder:nth-child(1)")
        if (groupViewToggle.value_of_css_property("display") != "none"):
            groupViewToggle.find_element(By.CSS_SELECTOR, "input").click()
            
        self.awaiter.until(EC.visibility_of_any_elements_located((By.CSS_SELECTOR, "label.ClinicalExam_sectionButton")))
        self.GetActiveTab().find_element(By.CSS_SELECTOR, "label.ClinicalExam_sectionButton").click()
        appointment = self.FillClinicalExamInfo(appointment)
        
        self.awaiter.until(EC.visibility_of_any_elements_located((By.CSS_SELECTOR, "label.DiagnosticsAndTreatments_sectionButton")))
        self.GetActiveTab().find_element(By.CSS_SELECTOR, "label.DiagnosticsAndTreatments_sectionButton").click()
        appointment = self.FillDiagnosticAndTreatmentInfo(appointment)
        
        
        
        
        
        return appointment
        

    def SaveAppointmentsForCurrentDate(self):
        appointments = []
        saveFileName = f"{self.CurrentDate.strftime('%Y-%m-%d')} Download.json"
        if (os.path.exists(f"In Progress Downloads/{saveFileName}")):
            with open(f"In Progress Downloads/{saveFileName}", "r") as file:
                appointments = jsonpickle.decode(file.read())
        else:
            appointments = self.GetAppointments(self.CurrentDate)
            
            with open(f"In Progress Downloads/{saveFileName}", "w") as file:
                file.write(jsonpickle.encode(appointments))
        
        filledAppointments = []
        if (os.path.exists(f"Complete Downloads/{saveFileName}")):
            with open(f"Complete Downloads/{saveFileName}", "r") as file:
                filledAppointments = jsonpickle.decode(file.read())
            
        for appointment in appointments:
            if appointment in filledAppointments:
                continue
            try:
                filledAppointments.append(self.FillAppointment(appointment))
            except Exception as e:
                self.logger.error(f"Error filling appointment {appointment.petName} with Dr. {appointment.doctor} on {appointment.appointmentDate} at {appointment.appointmentTime}: {repr(e)}:{e}\n{traceback.format_exc()}")
                continue
        
        with open(f"Complete Downloads/{saveFileName}", "w") as file:
            file.write(jsonpickle.encode(filledAppointments))
        
        
            
        




    def StartConversion(self):
        try:
            while self.CurrentDate < self.EndDate:
                self.SaveAppointmentsForCurrentDate()
                self.CurrentDate += datetime.timedelta(days=1)
        except BaseException as e:
            self.logger.error(f"An exception occurred on date {self.CurrentDate}: {e}\n{traceback.format_exc()}")
            







if __name__ == "__main__":
    with EZVetDownloader("settings.json") as converter:
        converter.StartConversion()


    
