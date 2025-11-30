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

# Local Imports
from AppointmentModel import AppointmentModel
from Utils import Utils


class EZVetDownloader:
    def __init__(self, settingsPath: str):
        # Initialize logger
        logging.basicConfig(filename='EZVetDownloader.log', )
        self.logger = logging.getLogger('EZVetDownloader')

        # Load settings to keep credentials out of code
        with open(settingsPath, 'r') as file:
            settings = json.load(file)
            self.user = settings['ezVet']['username']
            self.password = settings['ezVet']['password']
            self.url = settings['ezVet']['url']
            self.CurrentDate = datetime.strptime(settings['startDate'], "%Y-%m-%d").date()

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
        closableTabs = self.webDriver.find_elements(By.CSS_SELECTOR, "#right > div.tabSliderHolder > div > div[role=tablist] > div.recordTab button")
        for tab in closableTabs:
            tab.click()
            time.sleep(0.2)

    def GotoDay(self, toDate: date) -> bool:
        # Make sure we're on the dashboard
        self.CloseAllTabsButCalendar()
        
        # Wait for the mini calendar to load
        self.awaiter.until(EC.visibility_of_element_located((By.ID, "minical")))
        
        tries = 0
        while tries < 5:
            cal = self.webDriver.find_element(By.ID, "minical")
            if cal is None:
                self.logger.error("Could not find ezVet mini calendar!")
                continue
            time.sleep(3)
            if (self.webDriver.find_element(By.CSS_SELECTOR, "#currentdate > .current-day-active").text.strip().lower() != toDate.strftime("%A, %d %B %Y").lower()):
                break
            tries += 1
        if tries >= 5:
            raise Exception(f"Could not navigate to date {toDate} in ezVet after multiple tries!")
        

        # Make sure the correct month and year are present before selecting day
        yearSelector = Select(cal.find_element(By.CSS_SELECTOR, 'div > div:nth-child(1) > select:nth-child(4)'))
        yearSelector.select_by_visible_text(str(toDate.year))

        self.webDriver.implicitly_wait(1)  # Give time for the calendar to refresh

        monthSelector = Select(cal.find_element(By.CSS_SELECTOR, 'div > div:nth-child(1) > select:nth-child(2)'))
        monthSelector.select_by_visible_text(toDate.strftime("%B"))        

        # Select the day
        for row in range(2, 8):
            for column in range(1, 8):
                # Calendar gets rendered multiple times, so try a few times to get a non-stale element
                attempts = 0
                while attempts < 5:
                    try:
                        day = self.webDriver.find_element(By.CSS_SELECTOR, f'#minical > div > div:nth-child(3) > div.minicalrow_new:nth-child({row}) > div:nth-child({column}) > a')
                        if int(day.text) == toDate.day:
                            Utils.ForceClick(self.webDriver, day)
                            return True
                        break
                    except:
                        attempts += 1
                        time.sleep(0.5)
        return False
    

    def GetAppointments(self, getDate: date) -> List[AppointmentModel]:
        # Wait for the calendar to load
        self.awaiter.until(EC.visibility_of_element_located((By.ID, "calendar")))
        
        tries = 0
        while tries < 5:
            if not self.GotoDay(getDate):
                raise Exception(f"Could not navigate to date {getDate} in ezVet!")
            time.sleep(3)
            if (self.webDriver.find_element(By.CSS_SELECTOR, "#currentdate > .current-day-active").text.strip().lower() != getDate.strftime("%A, %d %B %Y").lower()):
                break
            tries += 1
        if tries >= 5:
            raise Exception(f"Could not navigate to date {getDate} in ezVet after multiple tries!")

        calendarWindow = self.webDriver.find_element(By.ID, "calendarmain")
        appointments: List[AppointmentModel] = []
        appointmentElements = self.webDriver.find_elements(By.CSS_SELECTOR, "#calendarmain > .theGrid > div.appt.hasQtip.dblClickOpen")
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

                if "patient" in title:
                    appointment.petName = value
                elif "case owner" in title:
                    appointment.doctor = value
                elif "owner" in title:
                    appointment.clientName = value
                elif "reason" in title:
                    appointment.reason = value
                elif "time" in title:
                    appointment.appointmentTime = value
                elif "type" in title:
                    appointment.type = value
            

            if appointment.HasBasicInfo():
                if 'ezVet' in appointment.clientName:
                    self.logger.warning(f"Skipping test appointment for {appointment.petName} with Dr. {appointment.doctor} on {appointment.appointmentDate} at {appointment.appointmentTime}")
                    continue
                appointments.append(appointment)
                self.logger.info(f"Found appointment for {appointment.petName} with Dr. {appointment.doctor} on {appointment.appointmentDate} at {appointment.appointmentTime}")
            else:
                self.logger.warning(f"Incomplete appointment found on {getDate} with text '{appointmentElement.text}', skipping.")
                
        return appointments

        
        
    def FillAppointment(self, appointment: AppointmentModel) -> AppointmentModel:
        self.GotoDay(appointment.appointmentDate)
        
        self.awaiter.until(EC.visibility_of_element_located((By.CSS_SELECTOR, appointment.cssPath)))
        
        appointment = self.webDriver.find_element(By.CSS_SELECTOR, appointment.cssPath)
        ActionChains(self.webDriver).double_click(appointment).perform()
        
        self.awaiter.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#rightpane > div.clinical > form > div.outerContent > .innerContent > div.detail > div.panels > div.subTab-details > div:first-child > div:first-child > div.sectionSelekta > label:nth-child(2) > input")))
        
        groupViewToggle = self.webDriver.find_element(By.CSS_SELECTOR, "#rightpane > div.clinical > form > div.outerContent > .innerContent > div.detail > div.panels > div.subTab-details > div:first-child > div:first-child > div.sectionSelekta > label:nth-child(2)")
        if (groupViewToggle.text.strip().lower() == "view by group"):
            groupViewToggle.find_element(By.CSS_SELECTOR, "input").click()
            
        
        sectionButton = lambda number: f"#rightpane > div.rtabdetails.clinical > form > div.outerContent > div > div.detail.hasSideBar > div > div.subTab-details > div:nth-child(1) > div:nth-child(1) > div.sectionSelekta > div:nth-child(2) > div.sectionSelektaGroups > label:nth-child({number}) > input"
        # Clinical Exam Section Info
        self.webDriver.find_element(By.CSS_SELECTOR, sectionButton(1)).click()
        
        
        
        
        
        
        return appointment
        

    def SaveAppointmentsForCurrentDate(self):
        appointments = []
        saveFileName = f"{self.CurrentDate.strftime('%Y-%m-%d')} Download.json"
        if (os.path.exists(f"In Progress Downloads/{saveFileName}")):
            with open(f"In Progress Downloads/{saveFileName}", "r") as file:
                appointments = jsonpickle.decode(file.read())
        else:
            appointments = self.GetAppointments(self.CurrentDate)
            
            with open(f"In Progress Downloads/{saveFileName}", "rw") as file:
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
            except:
                self.logger.error(f"Error filling appointment {appointment.petName} with Dr. {appointment.doctor} on {appointment.appointmentDate} at {appointment.appointmentTime}")
                continue
        
        with open(f"Complete Downloads/{saveFileName}", "rw") as file:
            file.write(jsonpickle.encode(filledAppointments))
        
        
            
        




    def StartConversion(self):
        try:
            appointments = self.GetAppointments(self.CurrentDate)
            self.logger.info(f"Found {len(appointments)} appointments on {self.CurrentDate}.")
            for appointment in appointments:
                self.GetAppointmentInfo(appointment)
        except Exception as e:
            self.logger.error(f"An exception occurred on date {self.CurrentDate}: {e}")
            







if __name__ == "__main__":
    with EZVetDownloader("settings.json") as converter:
        converter.StartConversion()


    
