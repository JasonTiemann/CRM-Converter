from typing import *
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import logging


class CovetrusUploader:
    def __init__(self, settingsPath: str):
        logging.basicConfig(filename='EZVetDownloader.log', )
        self.logger = logging.getLogger('EZVetDownloader')

        # Load settings to keep credentials out of code
        with open(settingsPath, 'r') as file:
            settings = json.load(file)
            self.covetrusUser = settings['covetrus']['username']
            self.covetrusPass = settings['covetrus']['password']
            self.covetrusUrl = settings['covetrus']['url']
        self.logger.info(f"""Loaded settings from {settingsPath}:
            User: {self.covetrusUser}
            Password: {'*' * len(self.covetrusPass)}
            URL: {self.covetrusUrl}
        """)

        self.webDriver = webdriver.Chrome()
        self.webDriver.get(self.covetrusUrl)
        self.webDriver.maximize_window()
        self.awaiter = WebDriverWait(self.webDriver, 10)


        def __enter__(self):
            return self
        def __exit__(self, excType, excValue, traceback):
            if (excType is not None):
                self.logger.error(f"An exception occurred on date {self.CurrentDate} for Patient {self.CureentPatient} belonging to {self.CurrentOwner}: {excValue}\n{traceback}")
            else:
                # Close the web driver when done (leave open if error to allow debugging)
                self.driver.quit()
                self.logger.info("Closed all web driver windows successfully.")
            logging.shutdown()

        def LogIn(self):
            self.logger.info("Checking for login page...")
            if "u/login" in self.webDriver.current_url:
                self.logger.info("Logging into covetrus...")
                
                loginForm = self.webDriver.find_element(By.ID, "widget-auth0-container")
                covetrusUsernameField = loginForm.find_element(By.ID, "username")
                covetrusPasswordField = loginForm.find_element(By.ID, "password")
                covetrusLoginButton = loginForm.find_element(By.CSS_SELECTOR, 'button[type=submit]')

                covetrusUsernameField.send_keys(self.covetrusUser)
                covetrusPasswordField.send_keys(self.covetrusPass)
                covetrusLoginButton.click()
                self.logger.info("covetrus login submitted.")
            else:
                self.logger.info("Already logged into ezcovetrus.")