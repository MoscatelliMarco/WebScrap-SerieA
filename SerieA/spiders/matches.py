import scrapy
from scrapy.selector import Selector

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException

import time

# DEBUGGING
import logging
import json


class MatchesSpider(scrapy.Spider):
    name = "matches"
    allowed_domains = ["www.legaseriea.it"]
    start_urls = ["https://www.legaseriea.it/it/serie-a"]

    # Take data from 2018 because before they have some inconsistencies

    def __init__(self):
        # Override the previous json
        with open('analyzed.json', 'w') as file:
            json.dump([], file, indent=4)
        
        chrome_options = Options()
        # chrome_options.add_argument('--headless')
        driver = webdriver.Chrome(options=chrome_options)

        # Load page and wait for it to load
        logging.info('Loading the page')
        driver.get("https://www.legaseriea.it/it/serie-a")
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//p[@class='p2 primary-400 medium ms-auto me-auto uppercase']")))
        time.sleep(.5)

        # Set a different window => needed later because the design of this window is more easy to scrape
        driver.set_window_size(1200, 900)

        # Calculate max day
        # If start_day == 1 that means that the season is finished so max_day is just a really large number
        current_day = self.find_curr_day(driver)
        if current_day != 1:
            max_day = current_day - 1
        else:
            max_day = 100

        current_day = 1
        while current_day <= max_day or not self.is_visible(after_btn):
            
            # Find all buttons that lead to matches
            matches_btn = driver.find_elements(By.XPATH, "//div[@class='d-lg-none d-block ms-auto']/a[@class='hm-button-icon']")

            for i, btn in enumerate(matches_btn):
                logging.info("Wait page load and remove popup")
                WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//div[@class='left d-flex align-content-around flex-wrap justify-content-center']")))
                time.sleep(.5)
                self.remove_popup(driver)

                # Reach the day with the match to analyze
                logging.info("Reach day")
                self.reach_day(current_day, driver)
                time.sleep(0.3)

                # Find the location of the match button and go there
                logging.info('Opening match link')
                match_btn = driver.find_element(By.XPATH, f"(//div[@class='d-lg-none d-block ms-auto']/a[@class='hm-button-icon'])[{i+1}]")
                driver.execute_script("arguments[0].scrollIntoView(true);", match_btn)
                # Adjustment needed to put the button in the window
                driver.execute_script("window.scrollBy(0, -250);")
                driver.get(match_btn.get_attribute('href'))

                # Element with all pages html
                self.pages = {}

                # Set a different window => needed later because the design of this window is more easy to scrape
                logging.info('Going into stats')
                WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "(//div[@class='hm-nav-section']/ul/li)[5]")))
                stats_btn = driver.find_element(By.XPATH, "(//div[@class='hm-nav-section']/ul/li/a)[5]")
                driver.get(stats_btn.get_attribute('href'))
                WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//a[@id='tab-general']")))
                time.sleep(.5)

                # Make all animations instant
                driver.execute_script("document.documentElement.style.scrollBehavior = 'auto';")

                # Remove popup and log
                logging.info("Removing popup and saving htmls of all data")
                self.remove_popup(driver)

                # Scrape all the general info
                self.pages['general'] = driver.page_source

                # Scrape all the possession info
                possession_btn = driver.find_element(By.ID, "tab-possession")
                driver.execute_script("arguments[0].scrollIntoView(true);", possession_btn)
                driver.execute_script("window.scrollBy(0, -250);")
                possession_btn.click()
                WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//p[contains(text(), 'Tempo di gioco totale')]")))
                time.sleep(.2)
                self.pages['possession'] = driver.page_source

                # Scrape all the passes info
                passes_btn = driver.find_element(By.ID, "tab-passes")
                passes_btn.click()
                WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "(//p[contains(text(), 'Passaggi riusciti')])[1]")))
                time.sleep(.2)
                self.pages['passes'] = driver.page_source

                # Scrape all the shots info
                shots_btn = driver.find_element(By.ID, "tab-shots")
                shots_btn.click()
                WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "(//p[contains(text(), 'Tiri totali')])[1]")))
                time.sleep(.2)
                self.pages['shots'] = driver.page_source

                self.parse_match(driver, current_day)

                driver.back()
                driver.back()

            current_day += 1

        input()

        # driver.close()

    def parse(self, response):
        pass

    def parse_match(self, driver, current_day):
        # Reading JSON from a file
        with open('analyzed.json', 'r') as file:
            data = json.load(file)

        # Writing JSON to a file
        # For now just writing the teams name for debugging porpuse
        with open('analyzed.json', 'w') as file:
            first_team = driver.find_element(By.XPATH, "(//h3[@class='medium black name-team'])[1]").text
            second_team = driver.find_element(By.XPATH, "(//h3[@class='medium black name-team'])[2]").text
            data.append({'1': first_team, '2': second_team})
            json.dump(data, file, indent=4)  # The 'indent' parameter is optional and makes the output pretty-printed

    def remove_popup(self, driver):
        # if there is popup about match
        try:
            # Attempt to find the element
            close_popup_btn = driver.find_element(By.XPATH, "//div[@class='left d-flex align-content-around flex-wrap justify-content-center']")
            # Click the element if it's found
            close_popup_btn.click()
        except NoSuchElementException:
            # If the element is not found, do nothing
            pass

    def is_visible(self, driver, element):
        # Wait for the element to be present in the DOM
        try:
            # Check if the element is visible in the viewport
            is_visible = driver.execute_script(
                "var elem = arguments[0],                 " \
                "  box = elem.getBoundingClientRect(),    " \
                "  cx = box.left + box.width / 2,         " \
                "  cy = box.top + box.height / 2,         " \
                "  e = document.elementFromPoint(cx, cy); " \
                "for (; e; e = e.parentElement) {         " \
                "  if (e === elem)                        " \
                "    return true;                         " \
                "}                                        " \
                "return false;                            ",
                element)
            return is_visible
        except NoSuchElementException:
            print("Element not found in the DOM")
        except TimeoutException:
            print("Timed out waiting for element to be present in the DOM")

    def reach_day(self, day_to_reach, driver):
        # Create a Select object
        select_input = driver.find_element(By.XPATH, "(//select)[1]")
        select = Select(select_input)

        # Find value and select it
        option = driver.find_element(By.XPATH, f"((//select)[1]/option[contains(text(), {day_to_reach})])[1]")
        value = option.get_property('value')
        select.select_by_value(value)

        time.sleep(.5)

    def find_curr_day(self, driver):
        # Find the current day that is being analyzed
        # Find the select input
        select_input = driver.find_element(By.XPATH, f"(//select)[1]")
        
        # Create a Select object and then get the selected object
        select = Select(select_input)
        selected_option = select.first_selected_option

        # Find the current day with a little bit of processing
        current_day = selected_option.text
        # Remove the last useless part: "° Giornata"
        current_day = current_day[:-10]
        print(selected_option.text)
        print(current_day)
        current_day = int(current_day)

        return current_day


    # def reach_day(self, day_to_reach, driver):

    #     current_day = self.find_curr_day(driver)

    #     # If current_day == 1 after button is not on the screen so go on day 2 to find it
    #     if current_day != 1:
    #         back_btn = driver.find_element(By.XPATH, "(//i[contains(text(), 'chevron_right')]/../parent::*[@class='d-flex align-items-center d-lg-none mt-3 mb-3']/div)[1]")
    #         after_btn = driver.find_element(By.XPATH, "(//i[contains(text(), 'chevron_left')]/../parent::*[@class='d-flex align-items-center d-lg-none mt-3 mb-3']/div)[2]")
    #     else:
    #         after_btn = driver.find_element(By.XPATH, "(//i[contains(text(), 'chevron_right')]/../parent::*[@class='d-flex align-items-center d-lg-none mt-3 mb-3']/div)")
    #         after_btn.click()
    #         time.sleep(.5)
    #         after_btn = driver.find_element(By.XPATH, "(//i[contains(text(), 'chevron_right')]/../parent::*[@class='d-flex align-items-center d-lg-none mt-3 mb-3']/div)[1]")

    #     unique_el = driver.find_element(By.XPATH, "(//p[@class='p4 dark-grey medium uppercase'])[2]").text

    #     # While cycle to reach the right day
    #     while current_day != day_to_reach:

    #         if current_day < day_to_reach:
    #             after_btn.click()

    #         if current_day > day_to_reach:
    #             back_btn.click()

    #         time.sleep(.15)

    #         # Cause of latency there might be some errors if I just change the value of current_day directly without scraping it directly from the website
    #         current_day = self.find_curr_day(driver)