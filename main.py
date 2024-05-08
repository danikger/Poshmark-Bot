from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC  
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from twocaptcha import TwoCaptcha
import requests

import time
import random
import os
from dotenv import load_dotenv

load_dotenv()

# LOGIN
username = os.getenv('LOGIN_USERNAME')
login_email = os.getenv('LOGIN_EMAIL')
login_password = os.getenv('LOGIN_PASSWORD')

# SETTINGS
shares_amount = 1050
shares_amount_my_closet = 400
share_my_closet = True
share_others_closets = False
follow_people = False


SCROLL_PAUSE_TIME = 2
lowest_share_like_time = 1.4
highest_share_like_time = 1.6
lowest_action_time = 0.5
highest_action_time = 1.0
completed_shares = 0


# CAPTCHA SOLVER
site_key = '6Lc6GRkTAAAAAK0RWM_CD7tUAGopvrq_JHRrwDbD'
service_key = os.getenv('2CAPTCHA_API_KEY')
solver = TwoCaptcha(service_key)


# ADDITIONAL FUNCTIONS -----------------------------------------
# Sleep functions to randomize the action speeds
def share_sleep():
    time.sleep(random.uniform(lowest_share_like_time, highest_share_like_time))


def action_sleep():
    time.sleep(random.uniform(lowest_action_time, highest_action_time))


def scroll_down_shares(items):
    # Get scroll height
    last_height = browser.execute_script("return document.body.scrollHeight")

    while (len(browser.find_elements(By.CLASS_NAME, 'share-gray-large'))) < items:
        # Scroll down to bottom
        browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # Wait to load page
        time.sleep(SCROLL_PAUSE_TIME)

        # Calculate new scroll height and compare with last scroll height
        new_height = browser.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    # Return to top of page
    browser.execute_script("window.scroll(0, 0);")


# Used to solve Google captchas. Uses 2captcha API to solve them.
def solve_captcha():
    time.sleep(3)
    browser.execute_script('var element=document.getElementsByClassName("g-recaptcha-response")[0]; element.style.display="";')

    print(solver.get_balance())

    pageurl = browser.current_url
    url = "http://2captcha.com/in.php?key=" + service_key + "&method=userrecaptcha&googlekey=" + site_key + "&pageurl=" + pageurl

    resp = requests.get(url)

    if resp.text[0:2] != 'OK':
        quit('Service error. Error code:' + resp.text)
    captcha_id = resp.text[3:]

    fetch_url = "http://2captcha.com/res.php?key=" + service_key + "&action=get&id=" + captcha_id

    while True:
        time.sleep(5)  # wait 5 sec.
        resp = requests.get(fetch_url)
        if resp.text[0:2] == 'OK':
            break
    time.sleep(20)
    # print(resp.text[3:])

    browser.execute_script("""document.getElementsByClassName("g-recaptcha-response")[0].innerHTML = arguments[0]""", resp.text[3:])

    browser.execute_script('var element=document.getElementsByClassName("g-recaptcha-response")[0]; element.style.display="none";')

    # Finds the path to the callback function inside the ___grecaptcha_cfg captcha object. Example: "___grecaptcha_cfg.clients[0].C.C.callback"
    # Credit: https://gist.github.com/2captcha/2ee70fa1130e756e1693a5d4be4d8c70
    captcha_data = browser.execute_script("""
        if (typeof (___grecaptcha_cfg) !== 'undefined') {
            return Object.entries(___grecaptcha_cfg.clients).map(([cid, client]) => {
            const data = { id: cid, version: cid >= 10000 ? 'V3' : 'V2' };
            const objects = Object.entries(client).filter(([_, value]) => value && typeof value === 'object');

            objects.forEach(([toplevelKey, toplevel]) => {
                const found = Object.entries(toplevel).find(([_, value]) => (
                value && typeof value === 'object' && 'sitekey' in value && 'size' in value
                ));
                
                if (found) {
                const [sublevelKey, sublevel] = found;

                data.sitekey = sublevel.sitekey;
                const callbackKey = data.version === 'V2' ? 'callback' : 'promise-callback';
                const callback = sublevel[callbackKey];
                if (!callback) {
                    data.callback = null;
                    data.function = null;
                } else {
                    data.function = callback;
                    const keys = [cid, toplevelKey, sublevelKey, callbackKey].map((key) => `['${key}']`).join('');
                    data.callback = `___grecaptcha_cfg.clients${keys}`;
                }
                }
            });
            return data;
            });
        }
        return [];""")

    # Path to the callback function inside the ___grecaptcha_cfg captcha object (Example: "___grecaptcha_cfg.clients[0].C.C.callback")
    callback_path = captcha_data[0]['callback']

    # Since there's no "submit" button for the captcha, we need to call the callback function manually
    browser.execute_script(f"window[{callback_path}](arguments[0])", resp.text[3:])

    # VVVVVVVVVV This works as well but you need to know the path to the callback function inside the ___grecaptcha_cfg captcha object. You can find the object by pasting this into the web console: "___grecaptcha_cfg.clients[0]"
    # browser.execute_script("""window[___grecaptcha_cfg.clients[0].C.C.callback](arguments[0])""", resp.text[3:])

    time.sleep(2)


# OPEN BROWSER -------------------------------------------------
fp = webdriver.FirefoxOptions()
fp.set_preference('dom.webdriver.enabled', False)

log = open("poshmark_log.txt", "a") # Log file to keep track of the bot's history (errors, successes, etc.)

browser = webdriver.Firefox(fp)
browser.get("https://poshmark.ca")

# Start time and start balance calculation variables
startTime = time.time()
startBalance = solver.get_balance()

# LOGIN --------------------------------------------------------
browser.find_element(By.CLASS_NAME, 'tc--m').click()
browser.implicitly_wait(10)

WebDriverWait(browser, 20).until(EC.presence_of_element_located((By.ID, 'login_form_username_email')))
emailElement = browser.find_element(By.ID, 'login_form_username_email')
passElement = browser.find_element(By.ID, 'login_form_password')

emailElement.send_keys(login_email)

passElement.send_keys(login_password)
passElement.submit()
time.sleep(3)
# Captcha solve
if browser.find_elements(By.CLASS_NAME, 'g-recaptcha-con'):
    solve_captcha()
    passElement.submit()


# MAIN ---------------------------------------------------------
if float(solver.get_balance()) < 0.5:
    message_text = 'Captcha solver balance is low! Current balance remaining: $' + str(solver.get_balance()) + '\n'
    log.write(message_text)


# Finds and removes the "turn on notifications" popup
element = browser.find_element(By.CLASS_NAME, 'soft__permission')
browser.execute_script("""var element = arguments[0]; element.parentNode.removeChild(element);""", element)

browser.implicitly_wait(0)


# FOLLOW PEOPLE -----------------------------------------------------------
if follow_people:
    WebDriverWait(browser, 20).until(EC.presence_of_element_located((By.XPATH, '//a[@href="/category/Women"]'))).click()

    time.sleep(5)
    WebDriverWait(browser, 20).until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'tile__creator')))[0].click()
    WebDriverWait(browser, 20).until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'closet__header__allow__display_handle_container')))[1].click()
    time.sleep(2)

    # Since this script is intended to run several times a day, it doesn't go crazy with the amount of follows. (Although you can keep scrolling and following as much as you want)
    for i in range(len(browser.find_elements(By.CSS_SELECTOR, '.btn--primary'))-5):
        browser.find_elements(By.CSS_SELECTOR, '.btn--primary')[1].click()
        time.sleep(random.uniform(0.4, 0.8))  # 0.4, 0.9time.sleep(1)
        if len(browser.find_elements(By.CSS_SELECTOR, '.modal__close-btn')) > 0:
            solve_captcha()


# SHARE MY CLOSET ---------------------------------------------------------
if share_my_closet:
    WebDriverWait(browser, 20).until(EC.presence_of_element_located((By.CLASS_NAME, 'dropdown__selector--caret')))
    browser.find_elements(By.CLASS_NAME, 'dropdown__selector--caret')[1].click()

    WebDriverWait(browser, 20).until(EC.presence_of_element_located((By.XPATH, '//a[@href="' + '/closet/' + username + '"]')))
    browser.find_element(By.XPATH, '//a[@href="' + '/closet/' + username + '"]').click()

    WebDriverWait(browser, 20).until(EC.presence_of_element_located((By.XPATH, "//input[@value='available']")))
    available_radio_button = browser.find_element(By.XPATH, "//input[@value='available']")

    browser.execute_script("arguments[0].scrollIntoView();", available_radio_button)
    browser.execute_script("arguments[0].click();", available_radio_button)

    if shares_amount_my_closet > 48:
        scroll_down_shares(shares_amount_my_closet)

    closet_size = len(browser.find_elements(By.CLASS_NAME, 'share-gray-large'))

    try:
        # Shares all items once, waits ~10 minutes, then shares all items again
        for x in range(2):
            for i in range(closet_size):
                WebDriverWait(browser, 20).until(EC.invisibility_of_element_located((By.CLASS_NAME, 'modal-backdrop')))
                WebDriverWait(browser, 20).until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'share-gray-large')))[i].click()
                if browser.find_elements(By.CLASS_NAME, 'g-recaptcha-con'):
                    solve_captcha()
                browser.find_element(By.CLASS_NAME, 'share-wrapper-container').click()
                share_sleep()
                if browser.find_elements(By.CLASS_NAME, 'g-recaptcha-con'):
                    solve_captcha()
                completed_shares += 1
            time.sleep(638)
    except Exception as e:
        message_text = 'Something went wrong. Only completed ' + str(completed_shares) + ' shares from your own closet. Reason: ' + str(e) + '.\n'
        print(e)

        print('The script took {0} seconds.'.format(time.time() - startTime))
        log.write(message_text)
        log.close()
        browser.quit()
        exit()

    time.sleep(5)

    message_text = 'Successfully completed ' + str(completed_shares) + ' shares from your own closet. The bot spent $' \
                   + str(round((float(startBalance) - float(solver.get_balance())), 5)) \
                        + ' on solving captchas this session.\n'
    log.write(message_text)
    log.close()


# SHARE OTHERS ---------------------------------------------------------
if share_others_closets:
    browser.find_element(By.XPATH, '//a[@href="' + '/category/Women' + '"]').click()

    if shares_amount > 48:
        scroll_down_shares(shares_amount)

    try:
        for i in range(shares_amount - 1):
            WebDriverWait(browser, 20).until(EC.invisibility_of_element_located((By.CLASS_NAME, 'modal-backdrop')))
            WebDriverWait(browser, 20).until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'share-gray-large')))[i].click()
            browser.find_element(By.CLASS_NAME, 'share-wrapper-container').click()
            share_sleep()
            if browser.find_elements(By.CLASS_NAME, 'g-recaptcha-con'):
                solve_captcha()
            completed_shares += 1
    except Exception as e:
        message_text = 'Something went wrong. Only completed ' + str(completed_shares) + ' shares. Reason: ' + str(e) + '.'

        print('The script took {0} seconds.'.format(time.time() - startTime))
        log.write(message_text)
        log.close()
        browser.quit()
        exit()

    time.sleep(5)

    message_text = 'Successfully completed ' + str(completed_shares) + ' shares. The bot spent $' + str(round((startBalance - solver.get_balance()), 5)) + ' on solving captchas this session.\n'

print('The script took {0} seconds.'.format(time.time() - startTime))
browser.quit()
log.close()
exit()