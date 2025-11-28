from selenium import webdriver
import json


class CRMConverter:
    def __init__(self, settingsPath):
        with open(settingsPath, 'r') as f:
            settings = json.load(f)
            self.EZVetUser = settings['ezVet']['username']
            self.EZVetPass = settings['ezVet']['password']
            self.EZVetURL = settings['ezVet']['url']
            
            self.covetrus_username = settings['covetrus']['username']
            self.covetrus_password = settings['covetrus']['password']
            self.covetrus_url = settings['covetrus']['url']
    
    # Additional methods for CRM conversion would go here