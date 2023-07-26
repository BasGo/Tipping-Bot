import os
import random
import sys
import json
from datetime import datetime
from datetime import timedelta
from time import sleep
import requests

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# Constants

BASE_URL = "https://www.kicktipp.de"
LOGIN_URL = "https://www.kicktipp.de/info/profil/login"
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH")

class Account:
    email : str
    password: str
    competition : str
    strategy: str
    high_diff_quotient: int
    overwrite_existing: bool
    hours_until_game: int

def read_config():
    with open("/etc/tipping-bot/accounts.json", "r") as file:
        accounts = json.load(file)

    for account_json in accounts:
        account = account_from_dict(account_json)
        execute(account)

def execute(account: Account):
    # output config variables
    outputAccountValues(account)

    #return
    # create driver
    try:
        if sys.argv[1] == 'headless':
            driver = webdriver.Chrome(
                options=set_chrome_options())  # for docker
        elif sys.argv[1] == 'local':
            driver = webdriver.Chrome(CHROMEDRIVER_PATH)  # for local
    except IndexError:
        print('Debug Mode\n')
        driver = webdriver.Chrome()  # debug

    # login
    driver.get(LOGIN_URL)

    # enter email
    driver.find_element(by=By.ID, value="kennung").send_keys(account.email)

    # enter password
    driver.find_element(by=By.ID, value="passwort").send_keys(account.password)

    # send login
    driver.find_element(by=By.NAME, value="submitbutton").click()

    # accept AGB
    try:
        driver.find_element(
            by=By.XPATH, value='//*[@id="qc-cmp2-ui"]/div[2]/div/button[2]').click()
    except NoSuchElementException:
        pass

    # entry form
    driver.get(F"https://www.kicktipp.de/{account.competition}/tippabgabe")

    count = driver.find_elements(by=By.CLASS_NAME, value="datarow").__len__()

    # iterate over rows of the form
    for i in range(1, count + 1):
        try:
             # get Team names
            homeTeam = driver.find_element(
                by=By.XPATH, value='//*[@id="tippabgabeSpiele"]/tbody/tr[' + str(i) + ']/td[2]').get_attribute('innerHTML')
            awayTeam = driver.find_element(
                by=By.XPATH, value='//*[@id="tippabgabeSpiele"]/tbody/tr[' + str(i) + ']/td[3]').get_attribute('innerHTML')

            # find entry, enter if empty
            homeTipEntry = driver.find_element(by=By.XPATH,
                                               value='//*[@id="tippabgabeSpiele"]/tbody/tr[' + str(i) + ']/td[4]/input[2]')
            awayTipEntry = driver.find_element(by=By.XPATH,
                                               value='//*[@id="tippabgabeSpiele"]/tbody/tr[' + str(i) + ']/td[4]/input[3]')

            homeTipValue = homeTipEntry.get_attribute('value')
            awayTipValue = awayTipEntry.get_attribute('value')

            # only calc tip and enter, when not entered already or overwrite set to True
            if account.overwrite_existing or (homeTipValue == '' and awayTipValue == ''):

                try:
                    # time of game
                    time = datetime.strptime(
                        driver.find_element(
                            by=By.XPATH, value='//*[@id="tippabgabeSpiele"]/tbody/tr[' + str(i) + ']/td[1]').get_property('innerHTML'),
                        '%d.%m.%y %H:%M')
                except ValueError:
                    pass

                # find quotes
                quotes = driver.find_element(
                    by=By.XPATH, value='//*[@id="tippabgabeSpiele"]/tbody/tr[' + str(i) + ']/td[5]/a').get_property('innerHTML').split(sep=" | ")

                # time until start of game
                timeUntilGame = time - datetime.now()
                print(F"{homeTeam} - {awayTeam} ({str(time.strftime('%d.%m.%y %H:%M'))}), Quotes: {str(quotes)}")

                # only tip if game starts in less than 2 hours
                if timeUntilGame < timedelta(hours=account.hours_until_game):
                    
                    tip = get_random_tip()
                    
                    # calculate tips bases on quotes and print them
                    if account.strategy == "quotes":
                        tip = calculate_tip(float(quotes[0]), float(quotes[1]), float(quotes[2]), account)

                    # send tips
                    print(F"Sending new tip: {tip[0]} - {tip[1]} (old was: {homeTipValue} - {awayTipValue})")
                    homeTipEntry.clear()
                    homeTipEntry.send_keys(tip[0])
                    awayTipEntry.clear()
                    awayTipEntry.send_keys(tip[1])

                    print()

                else:
                    print(F"Game starts in more than {account.hours_until_game} hours. Skipping...")
                    print()
            else:
                # print out the tipped game
                print(homeTeam + " - " + awayTeam)

                print("Game already tipped! Tip: " + homeTipEntry.get_attribute('value') + " - " + awayTipEntry.get_attribute('value'))
                print()

        except NoSuchElementException:
            continue
    sleep(0.1)

    # submit all tips
    driver.find_element(by=By.NAME, value="submitbutton").submit()

    try:
        if sys.argv[1] == 'local':
            print("Sleeping for 20secs to see the result - Debug Mode\n")
            sleep(20)
    except IndexError:
        pass

    driver.quit()

def get_random_tip():
    return random.randint(0, 2), random.randint(0, 2)
        
def calculate_tip(home, draw, away, account: Account):
    """ Calculates the tip based on the quotes"""

    # if negative the home team is more likely to win
    differenceHomeAndAway = home - away

    # generate random number between 0 and 1
    onemore = round(random.uniform(0, 1))

    # depending on the quotes, the factor is derived to decrease the tip for very unequal games
    coefficient = 0.3 if round(abs(differenceHomeAndAway)) > account.high_diff_quotient else 0.75

    # calculate tips
    if abs(differenceHomeAndAway) < 0.25:
        oneortwo = random.randint(1, 2)
        return oneortwo, oneortwo
    else:
        if differenceHomeAndAway < 0:
            return round(-differenceHomeAndAway * coefficient) + onemore, onemore
        elif differenceHomeAndAway > 0:
            return onemore, round(differenceHomeAndAway * coefficient) + onemore
        else:
            return onemore, onemore


def set_chrome_options() -> None:
    """Sets chrome options for Selenium.
    Chrome options for headless browser is enabled.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_prefs = {}
    chrome_options.experimental_options["prefs"] = chrome_prefs
    chrome_prefs["profile.default_content_settings"] = {"images": 2}
    return chrome_options

def account_from_dict(account_dict):
    a = Account()
    a.email = str(account_dict["email"])
    a.password = str(account_dict["password"])
    a.competition = str(account_dict["competition"])
    a.overwrite_existing = bool(account_dict["overwrite_existing"])
    a.high_diff_quotient = int(account_dict["high_diff_quotient"])
    a.hours_until_game = int(account_dict["hours_until_game"])
    a.strategy = str(account_dict["strategy"])
    return a

def outputAccountValues(account: Account):
    print("Current account:")
    print(F" - eMail = {account.email}")
    print(F" - Competition = {account.competition}")
    print(F" - Overwrite tips = {account.overwrite_existing}")
    print(F" - Strategy = {account.strategy}")
    print(F" - High diff quotient = {account.high_diff_quotient}")
    print(F" - Hours until game = {account.hours_until_game}")
    print()

def outputEnvValues():
    print("Current environment variables:")
    print(F" - CHROMEDRIVER_PATH = {CHROMEDRIVER_PATH}")
    print()

if __name__ == '__main__':
    while True:
        now = datetime.now().strftime('%d.%m.%y %H:%M')
        print(now + ": The script will execute now!\n")
        try:
            read_config()
        except Exception as e:
            print("An error occured: " + str(e) + "\n")
        now = datetime.now().strftime('%d.%m.%y %H:%M')
        print(now + ": The script has finished. Sleeping for 1 hour...\n")
        sleep(60*60)
