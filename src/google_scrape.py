import urllib.parse
from datetime import datetime
from typing import Generator

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
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
    encoded_str: str = urllib.parse.urlencode(search_params)
    encoded_query: str = f"{base_url}{encoded_str}"
    end_of_results: bool = False
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
            except WebDriverException:
                end_of_results = True
            yield search_results
        return "End of results"
    finally:
        driver.quit()

def google_search_scrape(search_terms: list[str]):
    base_url: str = "https://www.google.com/search?"
    for search_term in search_terms:
        driver = Driver(uc=True, headless=False, incognito=True)
        search_params: dict[str, str] = {
            "q": f"{search_term}",
            "tbm": "nws",
            "pws": "0",
            "tbs": "qdr:d",
            "sbd": "1"
        }
        page_num = 0
        for page in run_search(
                base_url=base_url,
                search_term=search_term,
                driver=driver,
                search_params=search_params
        ):
            for result in page:
                print(result.header_text)
    print("Done.")