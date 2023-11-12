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
        WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.XPATH, "//p[@class='p2 primary-400 medium ms-auto me-auto uppercase']")))
        time.sleep(.5)

        # Set a different window => needed later because the design of this window is more easy to scrape
        driver.set_window_size(1200, 1000)

        # Calculate max day
        # If start_day == 1 that means that the season is finished so max_day is the last element of the select input, else the one before the current_day after the page loads
        current_day = self.find_curr_day(driver)
        if current_day != 1:
            max_day = current_day - 1
        else:
            last_option = driver.find_element(By.XPATH, "(//select)[1]/option[last()]")
            max_day = last_option.text
            # Remove the last useless part: "° Giornata"
            max_day = max_day[:-10]
            max_day = int(max_day)


        current_day = 1
        while current_day <= max_day:

            # Analyze if JSON file and current_day are synchronized
            # I notice that if I don't do this part some times it skips days and this code fix that
            with open('analyzed.json', 'r') as file:
                data = json.load(file)
            try:
                if data[-1]['DAY'] + 1 != current_day:
                    current_day = data[-1]['DAY'] + 1
            except:
                pass
            
            # Find all buttons that lead to matches
            matches_btn = driver.find_elements(By.XPATH, "//div[@class='d-lg-none d-block ms-auto']/a[@class='hm-button-icon']")

            for i, btn in enumerate(matches_btn):
                logging.info("Wait page load and remove popup")
                WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//div[@class='left d-flex align-content-around flex-wrap justify-content-center']")))
                WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//div[@class='hm-block-title-with-border hm-container-spacing-top d-sm-flex align-items-end']")))
                time.sleep(.2)
                self.remove_popup(driver)

                # Reach the day with the match to analyze
                logging.info("Reach day")
                self.reach_day(current_day, driver)
                time.sleep(.7)

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
                time.sleep(.3)
                self.remove_popup(driver)
                stats_btn = driver.find_element(By.XPATH, "(//div[@class='hm-nav-section']/ul/li/a)[5]")
                driver.get(stats_btn.get_attribute('href'))
                logging.info("Going into match page")
                time.sleep(.2)
                try:
                    WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.XPATH, "//a[@id='tab-general']")))
                except TimeoutException:
                    logging.info("Could not load #tab-general")
                    # If even this one doesn't work just send a TimeoutError
                    WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.XPATH, "//a[@id='tab-possession']")))
                time.sleep(.2)

                # Make all animations instant
                driver.execute_script("document.documentElement.style.scrollBehavior = 'auto';")

                # Remove popup and log
                logging.info("Removing popup and saving htmls of all data")
                self.remove_popup(driver)

                # Scrape all the general info
                # Wait for the page to load, because I have noticed that in the saved data sometimes it doesn't include all metrics
                time.sleep(.2)
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

        driver.close()

    def parse(self, response):
        pass

    def parse_match(self, driver, current_day):

        # Reading JSON from a file
        with open('analyzed.json', 'r') as file:
            data = json.load(file)

        # Match data dict
        match_data = {}
        match_data['DAY'] = current_day

        # Transform html into scrapy response
        general_resp = Selector(text=self.pages['general'])

        # Get team names
        first_team_name = general_resp.xpath("(//h3[@class='medium black name-team'])[1]/text()").get()
        second_team_name = general_resp.xpath("(//h3[@class='medium black name-team'])[2]/text()").get()
        match_data['First Team Name'] = first_team_name
        match_data['Second Team Name'] = second_team_name
        
        # Scrape metrics for both teams
        first_team_general_metrics = general_resp.xpath("(//div[@class='hm-content-list-stats-match-center'])[1]/div[contains(@class, 'd-none')]/p[1]/text()").getall()
        second_team_general_metrics = general_resp.xpath("(//div[@class='hm-content-list-stats-match-center'])[1]/div[contains(@class, 'd-none')]/p[3]/text()").getall()
        # à changed in a even if grammatically incorrect because à returns an unicode in the json file
        metrics_name = ["Goal", "Occasioni Da Goal", "Assist", "Calci D'angolo", "Contrasti Vinti", "Contrasti Persi", "Palle Recuperate", "Palle Perse", "Falli Commessi", "Fuorigioco", "Parate", "Rigori", "Ammonizioni", "Doppie Ammonizioni", "Espulsioni", "Distanza Percorsa (km)", "Scatti", "Camminata (%)", "Corsa (%)", "Scatto (%)", "Dominio Territoriale", "Indice di pericolosita"]

        # Scraping donut indeces
        donut_indices = general_resp.css(".donut-percent::text").getall()
        first_team_general_metrics.append(donut_indices[0])
        first_team_general_metrics.append(donut_indices[1])
        second_team_general_metrics.append(donut_indices[4])
        second_team_general_metrics.append(donut_indices[5])

        logging.info(first_team_general_metrics)
        logging.info(second_team_general_metrics)
        print(len(first_team_general_metrics), len(second_team_general_metrics), len(metrics_name))

        for i, first_metric in enumerate(first_team_general_metrics):
            # Transform any percentage into an integer
            first_metric = first_metric.replace("%", "")
            first_metric = int(first_metric)
            match_data[f"FIRST {metrics_name[i]}"] = first_metric
        for i, second_metric in enumerate(second_team_general_metrics):
            # Transform any percentage into an integer
            second_metric = second_metric.replace("%", "")
            second_metric = int(second_metric)
            match_data[f"SECOND {metrics_name[i]}"] = second_metric

        # Writing JSON to a file
        # For now just writing the teams name for debugging porpuse
        with open('analyzed.json', 'w') as file:
            data.append(match_data)
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
        current_day = int(current_day)

        return current_day