import decimal
import time
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC

class Utils:
    @staticmethod
    def ForceClick(window, element):
        actions = ActionChains(window)
        actions.move_to_element(element).click().perform()

    @staticmethod
    def ScrollToElement(window, by, value):
        currentScroll = 0
        while EC.visibility_of_element_located((by, value)) == False and currentScroll < 10000:
            window.execute_script(f"document.querySelector('{value}').scrollTo(0, {currentScroll});")
            currentScroll += 100
            time.sleep(0.1)
        
    @staticmethod
    def ScrollToPosition(driver, position, id=None):
        driver.execute_script(f"{'window' if id is None else f'document.getElementById("{id}")'}.scrollTo(0, {position});")
        time.sleep(0.5)

    @staticmethod
    def HoverOverElement(window, element):
        actions = ActionChains(window)
        actions.move_to_element(element).perform()

    def GetStubbornElement(window, by, value, maxAttempts=5):
        attempts = 0
        while attempts < maxAttempts:
            try:
                element = window.find_element(by, value)
                if not element.is_displayed():
                    raise Exception("Stale Element")
                return element
            except:
                attempts += 1
                window.implicitly_wait(0.1)
        return None
    
    def GetCssSelector(window, element):
        path = ""
        currentElement = element
        depth = 0
        while True:
            tag = currentElement.tag_name
            classes = '.'.join(currentElement.get_attribute("class").strip().split(' '))
            id = currentElement.get_attribute("id")
            if id:
                path = f"#{id}" + (f" > {path}" if len(path) > 0 else "") 
                return path
            else:
                path = f"{tag}" + (f".{classes}" if classes else "") + (f" > {path}" if path else "")
                parent = currentElement.find_element("xpath", "..")
                if parent is None or parent.tag_name.lower() == "html":
                    return path
                currentElement = parent
            depth += 1
            if depth > 100:
                break
                
        raise Exception("Could not build CSS selector")
    
    
    @staticmethod
    def TryParse(parseString  : str, parseType : type):
        try:
            if parseType == int and '.' in parseString:
                return int(float(parseString))
            value = parseType(parseString)
            return value
        except Exception:
            return None
                    