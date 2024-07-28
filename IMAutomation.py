#IMAutomation - This e-commerce business uses a software called Internet Masterys to find items from retail stores and resell them on Amazon. I designed this program to fully automate my workload.
import re
import json
import openpyxl
import requests
from dotenv import load_dotenv
from os import getenv
from time import sleep
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

load_dotenv()

#WHAT RETAILER TO SOURCE PRODUCTS FROM
RETAILER = 'MACYS.COM'
PAGE = 1

#FILTER SETTING
ROI_MIN = 15
MONTHLY_MIN = 2.3
DAILY_MIN = 1
SPYWAIT = 12

#API SETTING
BASE_URL = 'https://api.internetmasterycommunity.com'
TOKEN = getenv('TOKEN')

def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def calculate_fee(asin, cost, sp, cc="USD", fba=True, market_id='ATVPDKIKX0DER'):
    endpoint = f'{BASE_URL}/spyrivals/amazon-feeV2'

    params = {
        "asin": asin,
        "costPrice": cost,
        "sellingPrice": sp,
        "currencyCode": cc,
        "fulfilledByAmazon": fba,
        "marketplaceId": market_id
    }

    headers = {
        "Authorization": TOKEN,
        "api-client": "browser"
    }

    res = requests_retry_session().get(endpoint, params=params, headers=headers)
    res.raise_for_status()
    feed = res.json()
    return feed

#ASCIN REGEX
ascin_regex = r'dp/([A-Z0-9]+)'

#PRICE REGEX
price_regex = r'(\d+\.\d{2})'

#PROVIDES AMAZON DATA - PREFERABLY WITH ASCIN
def spyrivals_search_v2(keyword):
    endpoint = f'{BASE_URL}/spyrivals/searchV2'

    headers = {
        "Authorization": TOKEN,
        "api-client": "browser",
        "Content-Type": "application/json"
    }
    res = requests_retry_session().post(endpoint, json=keyword, headers=headers)
    res.raise_for_status()
    return res.json()

def get_lowest_price(product_data):
    product = list(product_data['products'].values())[0]
    lowest_prices = product.get('LowestPrices', [])

    amazon_price = None
    merchant_price = None

    for price_info in lowest_prices:
        if price_info['fulfillmentChannel'] == 'Amazon':
            amazon_price = price_info['LandedPrice']['Amount']
        elif price_info['fulfillmentChannel'] == 'Merchant':
            merchant_price = price_info['LandedPrice']['Amount']

    if amazon_price is not None:
        return amazon_price
    elif merchant_price is not None:
        return merchant_price
    else:
        return None

#SINCE ITEMS HAVE THESE STATS ON THE WEBSITE, IT MAKES SENSE TO BE ITS OWN DATA TYPE
class BoloItem:
    def __init__(self, title, retailer_link, amazon_link, monthly_sales, daily_sales, vendor, ascin, sell_price, profit, roi, cost_price):
        self.title = title
        self.retailer_link = retailer_link
        self.amazon_link = amazon_link
        self.monthly_sales = monthly_sales
        self.daily_sales = daily_sales
        self.vendor = vendor
        self.ascin = ascin
        self.sell_price = f'${sell_price}'
        self.profit = f'${profit:.2f}'
        self.roi = f'{roi:.2f}%'
        self.cost_price = f'${cost_price}'

    def create_row(self, ws):
        ws.append([self.ascin, self.title, self.vendor, self.amazon_link, self.retailer_link, self.monthly_sales, self.daily_sales, self.cost_price, self.sell_price, self.profit, self.roi])

    def pprint(self):
        print(f'Title: {self.title}')
        print(f'Retail Link: {self.retailer_link}')
        print(f'Amazon Link: {self.amazon_link}')
        print(f'Monthly Sales: {self.monthly_sales}')
        print(f'Daily Sales: {self.daily_sales}')
        print(f'Vendor: {self.vendor}')
        print(f'ascin: {self.ascin}')
        print(f'Sell Price: {self.sell_price}')
        print(f'Buy Price: {self.cost_price}')
        print(f'Profit: {self.profit}')
        print(f'ROI: {self.roi}')


#RETURNS ASCIN, SALES, RETAIL WEBSITE, AND AMAZON WEBSITE
def key_info(row):
    amazon_listing = row.find_element(By.CSS_SELECTOR, "a.text-decoration-none.black--text")
    retail_listing = row.find_element(By.CSS_SELECTOR, "a.text-decoration-none.body-1")
    sales = row.find_elements(By.CSS_SELECTOR, "span.body-1")
    ascin= re.search(ascin_regex, amazon_listing.get_attribute('href')).group(1)
    return amazon_listing, retail_listing, sales, ascin

#GET MACYS PRICES IF IT'S AVAILABLE
def macys_prices(url):
    macys = firefox()
    macys.get(retail_listing.get_attribute('href'))
    macys_soup = BeautifulSoup(macys.page_source, 'html.parser')
    cost_price = macys_soup.find('div', 'lowest-sale-price')
    unavailable = macys_soup.find('p', 'p-not-avail-lbl c-red large margin-bottom-s medium-margin-top-xxs')
    macys.quit()
    if cost_price:
        match = re.search(price_regex, cost_price.text)
        if match:
            return float(match.group(1))
        else:
            return None
    elif unavailable:
        return None
    return None



#MY BOSS USERNAME AND PASSWORD - YES HE ACTUALLY DID SHARED HIS ACCOUNT WITH ALL OF US
USERNAME = getenv('USERNAME')
PASSWORD = getenv('PASSWORD')
URL = f'https://app.internetmasterycommunity.com/bolo-search?roi[min]={ROI_MIN}&monthlyEstBuy[min]={MONTHLY_MIN}&dailyEstBuy[min]={DAILY_MIN}&keyword={RETAILER}&page={PAGE}'

#SELENIUM SETTING
def firefox():
    options = FirefoxOptions()
    options.add_argument("--headless")
    return webdriver.Firefox(options=options)

if __name__ == '__main__':
    browser = firefox()
    browser.get(URL)
    wait = WebDriverWait(browser, 10)
    username_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#input-33')))
    username_box.send_keys(USERNAME)
    password_box = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#input-36')))
    password_box.send_keys(PASSWORD)
    password_box.send_keys(Keys.ENTER)

    sleep(5)

    i = 1

    while True:
        try:
            table_rows = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//tr[@class='']")))
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(['ASCIN', 'TITLE', 'VENDOR', 'AMAZON LINK', 'MACYS LINK', 'MONTHLY SALES', 'DAILY SALES', 'BUY PRICE', 'SELL PRICE', 'PROFIT', 'ROI'])
            print(f'Creating table{i}.xlsx')
            for row in table_rows:
                #SCRAPE DATA
                amazon_listing, retail_listing, sales, ascin = key_info(row)

                if not amazon_listing:
                    continue

                try:
                    keyword = spyrivals_search_v2({
                        "keywords": ascin,
                    })
                except:
                    continue

                sell_price = get_lowest_price(keyword)

                cost_price = macys_prices(retail_listing.get_attribute('href'))

                if cost_price is None:
                    continue

                try:
                    fees = calculate_fee(ascin, cost_price, sell_price).get('fee', 0)
                    profit = sell_price - cost_price - fees
                    roi = profit / cost_price * 100
                except:
                    continue

                #BoloItem details
                item = BoloItem(
                    amazon_listing.text,
                    retail_listing.get_attribute('href'),
                    amazon_listing.get_attribute('href'),
                    sales[1].text,
                    sales[2].text,
                    RETAILER,
                    ascin,
                    sell_price,
                    profit,
                    roi,
                    cost_price
                )

                item.pprint()

                item.create_row(ws)

            wb.save(f'table{i}.xlsx')
            print(f'table{i}.xlsx is finished!')
            i = i + 1
            try:
                nxt_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.v-pagination__navigation[aria-label="Next page"]')))
                browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", nxt_btn)
                nxt_btn.click()
            except ElementClickInterceptedException:
                browser.execute_script("arguments[0].click();", next_button)

        except Exception as err:
            browser.quit()
            print('All done', err)
            break

