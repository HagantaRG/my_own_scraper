import logging
from datetime import datetime
from json import loads
from time import sleep

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from seleniumbase import Driver

from utils.news_utils import NewsInformation
from utils.scraper_utils import write_info_to_csv, check_run_done

logger = logging.getLogger(__name__)

# TODO: Standardise  variable names.
def scrape_hkx(keywords: list[str]) -> None:
    count = 0
    scrape_link: str = "https://www1.hkexnews.hk/listedco/listconews/index/lci.html?lang=en"
    driver = Driver(uc=True, headless=True)
    logger.info(f"Starting scrape for {scrape_link}")
    last_page: bool = False
    driver.get(scrape_link)
    days_button: WebElement = driver.find_element(By.CLASS_NAME, "sevenDays")
    days_button.click()
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "onetrust-reject-all-handler"))
        )
        logger.info("Found reject button in HKX, clicking.")
        driver.find_element(By.ID, "onetrust-reject-all-handler").click()
        WebDriverWait(driver, 5).until(
            EC.invisibility_of_element_located((By.ID, "onetrust-group-container"))
        )
    except TimeoutException:
        pass
    more_button: WebElement = driver.find_element(By.CSS_SELECTOR, ".component-loadmore__link.component-loadmore__icon")
    WebDriverWait(driver, 2).until(
        EC.element_to_be_clickable(more_button)
    )
    more_button.click()
    try:
        while not last_page:
            logger.info(f"Waiting for element presence in {scrape_link}")
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "table-scroller"))
            )
            sleep(5)
            table_scroller: WebElement = driver.find_element(By.CLASS_NAME, "table-scroller")
            announcements_table_body: WebElement = table_scroller.find_element(
                By.TAG_NAME,
                "tbody"
            )
            logger.info(f"Retrieving announcements for {scrape_link}")
            announcements: list[WebElement] = announcements_table_body.find_elements(By.TAG_NAME, "tr")
            logger.info(f"Found {len(announcements)} announcements, parsing...")
            for announcement in announcements:
                # Get link for announcement content
                announcement_details: list[WebElement] = announcement.find_elements(
                    By.TAG_NAME,
                    "td"
                )
                announcement_title: str = announcement_details[3].text
                announcement_stock_name: str = announcement_details[2].text
                announcement_link: str = announcement_details[3].find_element(By.CLASS_NAME, "doc-link").find_element(By.TAG_NAME, "a").get_attribute("href")
                logger.debug(f"looking through {announcement_title}")
                announcement_date: datetime = datetime.strptime(
                    announcement_details[0].text,
                    "%d/%m/%Y %H:%M"
                )

                relevant_keywords: list[str] = [keyword for keyword in keywords if
                                                keyword in f"{announcement_title}{announcement_stock_name}".upper()]

                news_info: NewsInformation = NewsInformation(
                    news_link=announcement_link,
                    news_date=announcement_date,
                    news_title=announcement_title,
                    retrieved_at=datetime.now(),
                    relevant_keywords=relevant_keywords if len(relevant_keywords) > 0 else [""]
                )

                if check_run_done(news_info):
                    last_page = True
                    break

                if news_info.relevant_keywords != [""]:
                    write_info_to_csv(news_info)

                count += 1
            logger.info(f"Done scraping HKX, scraped total of {count} announcements")
    finally:
        driver.quit()

def scrape_sgx(keywords: list[str]) -> None:
    page_num: int = 1
    last_page: bool = False
    driver = Driver(uc=True, headless=True)
    count: int = 0
    try:
        while not last_page:
            scrape_link: str = f"https://www.sgx.com/securities/company-announcements?page={page_num}&pagesize=200"
            logger.info(f"Starting scrape for {scrape_link}")
            driver.get(scrape_link)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "tr"))
            )
            logger.info(f"Retrieving announcements for {scrape_link}")
            announcements: list[WebElement] = driver.find_element(
                By.CLASS_NAME,
                "sgx-content-table-scroll-container"
            ).find_element(
                By.TAG_NAME,
                "table"
            ).find_element(
                By.TAG_NAME,
                "tbody"
            ).find_elements(
                By.TAG_NAME,
                "tr"
            )
            logger.info(f"Found {len(announcements)} announcements, parsing...")
            for announcement in announcements:
                announcement_data: list[WebElement] = announcement.find_elements(By.TAG_NAME, "td")
                announcement_date: datetime = datetime.strptime(
                    announcement_data[0].text,
                    "%d %b %Y %H:%M %p"
                )
                issuer_name: str = announcement_data[1].text
                security_name: str = announcement_data[2].text
                title: str = announcement_data[3].text
                logger.debug(f"Looking through {title}{issuer_name}{security_name}")
                link: str = announcement_data[3].find_element(By.TAG_NAME, "a").get_attribute("href")
                relevant_keywords: list[str] = [keyword for keyword in keywords if
                                                keyword in f"{title}{issuer_name}{security_name}".upper()]
                news_info: NewsInformation = NewsInformation(
                    news_link=link,
                    news_date=announcement_date,
                    news_title=title,
                    retrieved_at=datetime.now(),
                    relevant_keywords=relevant_keywords if len(relevant_keywords) > 0 else [""]
                )

                if check_run_done(news_info):
                    last_page = True
                if news_info.relevant_keywords != [""]:
                    write_info_to_csv(news_info)
                count += 1
                if last_page:
                    break
            if not last_page:
                logger.info(
                     f"Not at end of relevant announcements for SGX after {count} docs scraped, going to next page."
                )
                page_num += 1
        logger.info(f"Done scraping SGX, scraped total of {count} announcements")
    finally:
        driver.quit()

def scrape_bursa_my(keywords: list[str]) -> None:
    ## Use their API, you can probably access it.
    count = 0
    current_time: int = int(datetime.now().timestamp())
    page_count: int = 0
    last_page: bool = False
    driver = Driver(uc=True, headless=True)
    try:
        logger.info(f"Starting scrape for https://www.bursamalaysia.com/")
        while not last_page:
            page_count += 1
            scrape_link: str = f"https://www.bursamalaysia.com/api/v1/announcements/search?ann_type=company&per_page=50&page={page_count}&_={current_time}"
            driver.get(scrape_link)
            announcement_json_str: str = driver.page_source.split("<pre>")[1].split("</pre>")[0]
            announcement_json: dict = loads(announcement_json_str)
            data: list[list[str|int]] = announcement_json["data"]
            for entry in data:
                date_str: str = entry[1].split("d-none'>")[1].split("</div>")[0]
                link_ext: str = entry[3].split("href='")[1].split("' target=")[0]
                link: str = f"https://bursamalaysia.com{link_ext}"
                company_name: str = entry[2].split("_blank>")[1].split("</a")[0] if entry[2] != '-' else ""
                title: str = entry[3].split("_blank>")[1].split("</a")[0]
                relevant_keywords: list[str] = [keyword for keyword in keywords if keyword in f"{title}{company_name}".upper()]
                announcement_date: datetime = datetime.strptime(
                    date_str,
                    "%d %b %Y"
                )
                news_info: NewsInformation = NewsInformation(
                    news_link=link,
                    news_date=announcement_date,
                    news_title=title,
                    retrieved_at=datetime.now(),
                    relevant_keywords=relevant_keywords if len(relevant_keywords) > 0 else [""]
                )

                if check_run_done(news_info):
                    last_page = True
                if news_info.relevant_keywords != [""]:
                    write_info_to_csv(news_info)
                if last_page:
                    break
                count += 1
            if not last_page:
                logger.info(
                    f"Not at end of relevant announcements for Malaysia after {count} docs scraped, going to next page."
                )
        logger.info(f"Done scraping Malaysian exchange, scraped total of {count} announcements")
    finally:
        driver.quit()

def scrape_szse(keywords: list[str]) -> None:
    page_num: int = 1
    last_page: bool = False
    driver = Driver(uc=True, headless=True)
    count: int = 0
    scrape_link: str = f"https://www.szse.cn/disclosure/listed/notice/index.html"
    logger.info(f"Starting scrape for {scrape_link}")
    driver.get(scrape_link)
    try:
        while not last_page:
            logger.info(f"SZSE page {page_num} scraping...")
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".disclosure-tbody > tr"))
            )
            announcements: list[WebElement] = driver.find_elements(By.CSS_SELECTOR, ".disclosure-tbody > tr")

            for announcement in announcements:
                announcement_details: list[WebElement] = announcement.find_elements(By.TAG_NAME, "td")
                announcement_stock_code: str = announcement_details[0].find_element(By.TAG_NAME, "a").text
                announcement_stock_name: str = announcement_details[1].find_element(By.TAG_NAME, "a").text
                announcement_files: list[WebElement] = announcement_details[2].find_elements(By.TAG_NAME, "a")
                date_text: str = announcement_details[3].find_elements(By.TAG_NAME, "span")[0].text
                # This date extraction is because the Shenzhen stock exchange for some reason uses *TWO* datetime formats.
                announcement_date: datetime = datetime.strptime(
                    date_text.split(" ")[0], "%Y-%m-%d"
                )
                for file in announcement_files:
                    count += 1
                    announcement_title: str = file.get_attribute("data-title")
                    announcement_link: str = file.get_attribute("href")
                    search_str: str = f"{announcement_title}{announcement_stock_code}{announcement_stock_name}"
                    relevant_keywords: list[str] = [keyword for keyword in keywords if
                                                    keyword in f"{search_str}".upper()]
                    news_info: NewsInformation = NewsInformation(
                        news_link=announcement_link,
                        news_date=announcement_date,
                        news_title=announcement_title,
                        retrieved_at=datetime.now(),
                        relevant_keywords=relevant_keywords if len(relevant_keywords) > 0 else [""]
                    )
                    if news_info.relevant_keywords != [""]:
                        write_info_to_csv(news_info)
                    logger.debug(f"{announcement_stock_code} {announcement_title} {announcement_link}")

            paginator: WebElement = driver.find_element(By.ID, "paginator")
            this_page: WebElement = paginator.find_element(By.CSS_SELECTOR, f"a[data-pi=\"{page_num-1}\"]")
            if "last" in this_page.get_attribute("class"):
                logger.info(f"Last page of SZSE reached. Ending.")
                break
            else:
                logger.info(
                    f"Not at end of relevant announcements for SZSE after {count} docs scraped, going to next page."
                )
                page_num += 1
                paginator.find_element(By.CSS_SELECTOR, ".next > a").click()
                WebDriverWait(driver, 30).until(
                    EC.staleness_of(announcements[1])
                )
    finally:
            driver.quit()

def scrape_sse(keywords: list[str]) -> None:
    page_num: int = 0
    last_page: bool = False
    driver = Driver(uc=True, headless=True)
    scrape_link: str = f"https://www.sse.com.cn/disclosure/listedinfo/announcement/"
    logger.info(f"Starting scrape for {scrape_link}")
    driver.get(scrape_link)
    logger.info(f"Waiting for page to fully load...")
    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.TAG_NAME, "tr"))
    )
    table_entry: WebElement = driver.find_element(By.TAG_NAME, "tr")
    logger.info(f"Clicking button to get last three days of info...")
    date_range_button: WebElement = driver.find_element(By.CLASS_NAME, "range_date")
    date_range_button.click()
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "laydate-btns-latestThree"))
    )
    three_day_button: WebElement = driver.find_element(By.CLASS_NAME, "laydate-btns-latestThree")
    three_day_button.click()
    WebDriverWait(driver, 30).until(
        EC.staleness_of(table_entry)
    )
    count: int = 0
    while not last_page:
        page_num += 1
        logger.info(f"SSE page {page_num} scraping...")
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.TAG_NAME, "tbody"))
        )
        table_body: WebElement = driver.find_element(By.TAG_NAME, "tbody")
        announcements: list[WebElement] = table_body.find_elements(
            By.TAG_NAME,"tr"
        )
        for announcement in announcements:
            count += 1
            ann_class: str = announcement.get_attribute("class")
            logger.debug(f"{count} {ann_class}")
            announcement_details: list[WebElement] = announcement.find_elements(By.TAG_NAME, "td")
            announcement_link: str = announcement_details[2].find_element(By.TAG_NAME, "a").get_attribute("href")
            date_text: str = announcement_details[5].text
            announcement_date: datetime = datetime.strptime(
                date_text, "%Y-%m-%d"
            )
            if "multiple_bag" in ann_class and "first_bag" not in ann_class:
                pass
            else:
                announcement_stock_code: str = announcement_details[0].find_element(By.TAG_NAME, "a").text
                announcement_stock_name: str = announcement_details[1].find_element(By.TAG_NAME, "a").text
            announcement_title: str = announcement_details[2].find_element(By.TAG_NAME, "a").text
            search_str: str = f"{announcement_title}{announcement_stock_code}{announcement_stock_name}"
            relevant_keywords: list[str] = [keyword for keyword in keywords if
                                            keyword in f"{search_str}".upper()]
            news_info: NewsInformation = NewsInformation(
                news_link=announcement_link,
                news_date=announcement_date,
                news_title=announcement_title,
                retrieved_at=datetime.now(),
                relevant_keywords=relevant_keywords if len(relevant_keywords) > 0 else [""]
            )
            logger.debug(f"{announcement_title}")
            if check_run_done(news_info):
                last_page = True
            if news_info.relevant_keywords != [""]:
                write_info_to_csv(news_info)
            if last_page:
                break
        if not last_page:
            logger.info(
                f"Not at end of relevant announcements for SSE after {count} docs scraped, going to next page."
            )
            next_button: WebElement = driver.find_element(By.CLASS_NAME, "next").find_element(By.TAG_NAME, "a")
            next_button.click()
            WebDriverWait(driver,30).until(
                EC.staleness_of(announcements[0])
            )
        else:
            logger.info(f"Last page of SSE reached. Ending.")
