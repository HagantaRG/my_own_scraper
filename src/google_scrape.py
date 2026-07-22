import urllib.parse
from datetime import datetime
from typing import Generator
from time import sleep
import logging

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from seleniumbase import Driver
from seleniumbase.core.sb_driver import DriverMethods

# N.B the important thing here really is that this thing will likely need to be updated like. Quarterly. Or something.
# so it should send out emails on failure.
class SearchResult:
    header_text: str
    res_link: str
    date: datetime
    search_term: str
    def __init__(self, header_text: str, res_link: str, date: datetime, search_term: str):
        self.header_text = header_text
        self.res_link = res_link
        self.date = date
        self.search_term = search_term

def run_search(
        base_url: str,
        search_term: str,
        search_params: dict[str,str],
        driver: DriverMethods,
) -> Generator[list[SearchResult], None, str]:
    search_params["q"] = search_term
    encoded_str: str = urllib.parse.urlencode(search_params)
    encoded_query: str = f"{base_url}{encoded_str}"
    end_of_results: bool = False

    # This could be its own class, I guess.
    # If I want to make a lib. for this, it will need to be able to handle *all* different search modes.

    try:
        driver.get(encoded_query)
        driver.add_cookie({
            "name": "SOCS",
            "value": "CAESNQgCEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjYwNzEyLjE1X3AwGgJlbiACGgYIgNXQ0gY",
            "domain": ".google.com",
            "path": "/",
        })
        while not end_of_results:
            search_results: list[SearchResult] = []
            driver.get(encoded_query)
            sleep(3)
            search_element_children: list[WebElement] = driver.find_elements(By.CSS_SELECTOR, "[id=\"search\"] *")
            if len(search_element_children) == 0:
                logging.info(f"No results found for search term {search_params["q"]}")
                end_of_results = True
                continue
            driver.wait_for_element_present(By.CSS_SELECTOR, "div [id=\"search\"] div[data-ved] > div[data-hveid]")
            date_elements: list[WebElement] = driver.find_elements(By.CSS_SELECTOR, "span[data-ts]")
            dates: list[datetime] = [
                datetime.fromtimestamp(float(date_element.get_attribute("data-ts"))) for date_element in date_elements
            ]
            headings: list[WebElement] = driver.find_elements(
                By.CSS_SELECTOR,
                "div[data-news-cluster-id] div[role=\"heading\"]"
            )
            links: list[WebElement] = driver.find_elements(
                By.CSS_SELECTOR,
                "div[data-news-cluster-id] > a[href]"
            )
            for index, element in enumerate(headings):
                search_results.append(
                    SearchResult(
                        header_text=element.text,
                        res_link=links[index].get_attribute("href"),
                        date =dates[index],
                        search_term=search_term
                    )
                )
            try:
                next_button: WebElement = driver.find_element(By.CSS_SELECTOR, "a[id=\"pnnext\"]")
                encoded_query = next_button.get_attribute("href")
                logging.info(f"Going to next page for search term {search_params["q"]}")
            except WebDriverException:
                end_of_results = True
                logging.info(f"End of results reached for {search_params["q"]}")
                continue
            yield search_results
        return "End of results"
    finally:
        driver.quit()

def google_search_scrape(sheet_dict: dict[str, list[str]]) -> dict[str, list[SearchResult]]:
    search_terms: list[str] = sheet_dict["google_search_terms"]
    base_url: str = "https://www.google.com/search?"
    res_dict: dict[str, list[SearchResult]] = {}
    for search_term in search_terms:
        logging.info(f"Starting search scrape for {search_term}")
        driver = Driver(uc=True, headless=False, incognito=True)
        search_params: dict[str, str] = {
            "tbm": "nws",
            "pws": "0",
            "tbs": "qdr:d",
            "sbd": "1"
        }
        res_dict[search_term] = []
        for page in run_search(
                base_url=base_url,
                search_term=search_term,
                driver=driver,
                search_params=search_params
        ):
            res_dict[search_term] += page
        logging.info(f"Done scraping {search_term}")
    return res_dict