import calendar
import codecs
import logging
from datetime import UTC, datetime, timedelta, timezone
from json import loads
from zoneinfo import ZoneInfo

from curl_cffi import requests as cffi_requests
from requests import get
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from seleniumbase import Driver
from seleniumbase.core.sb_driver import WebDriver

from src.scrapers.helpers import (
    RunTally,
    log_run_results,
    parse_announcement,
)

logger = logging.getLogger(__name__)
GMT_PLUS_7 = timezone(timedelta(hours=7))
HONG_KONG_TIME = ZoneInfo("Asia/Hong_Kong")
SINGAPORE_TIME = ZoneInfo("Asia/Singapore")
KUALA_LUMPUR_TIME = ZoneInfo("Asia/Kuala_Lumpur")
SHENZHEN_TIME = ZoneInfo("Asia/Shanghai")
SHANGHAI_TIME = ZoneInfo("Asia/Shanghai")

# Defines max retries for all retry-supporting steps.
max_tries: int = 5






def scrape_hkx(sheet_dict: dict[str, list[str]]) -> None:
    keywords: list[str] = sheet_dict["keywords"]
    scrape_link: str = (
        "https://www1.hkexnews.hk/listedco/listconews/index/lci.html?lang=en"
    )
    driver = Driver(uc=True, headless=True)
    tally = RunTally()
    try:
        logger.info(f"Starting scrape for {scrape_link}")
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

        cutoff_date: datetime = datetime.now(GMT_PLUS_7) - timedelta(hours=36)
        last_datetime: datetime | None = None
        logger.info(f"Waiting for element presence in {scrape_link}")
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tbody > tr > td"))
        )
        logger.info(f"Retrieving announcements for {scrape_link}")
        announcements: list[WebElement] = []
        num_last_announcements: int = len(announcements)

        def rows_finished_loading(webdriver: WebDriver) -> bool:
            return not webdriver.find_elements(
                By.CSS_SELECTOR, ".loading, .spinner, [aria-busy='true']"
            )

        while last_datetime is None or last_datetime > cutoff_date:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            try:
                more_button: WebElement | None = WebDriverWait(driver, 1).until(
                    EC.element_to_be_clickable(
                        (
                            By.CSS_SELECTOR,
                            ".component-loadmore__link.component-loadmore__icon",
                        )
                    )
                )
            except TimeoutException:
                more_button = None
            if more_button is not None:
                more_button.click()
            WebDriverWait(driver, 60).until(rows_finished_loading)
            announcements = driver.find_elements(By.CSS_SELECTOR, "tbody > tr")
            announcement_details: list[WebElement] = announcements[-1].find_elements(
                By.TAG_NAME, "td"
            )
            announcement_datetime: datetime = datetime.strptime(
                announcement_details[0].text, "%d/%m/%Y %H:%M"
            ).replace(tzinfo=HONG_KONG_TIME)

            if (
                announcement_datetime != last_datetime
                or len(announcements) > num_last_announcements
            ):
                last_datetime = announcement_datetime
                num_last_announcements = len(announcements)
            else:
                break

        logger.info(f"Found {len(announcements)} announcements, parsing...")

        for announcement in announcements:
            # Get link for announcement content
            announcement_details: list[WebElement] = announcement.find_elements(
                By.TAG_NAME, "td"
            )
            announcement_title: str = announcement_details[3].text
            announcement_stock_name: str = announcement_details[2].text
            announcement_link: str = (
                announcement_details[3]
                .find_element(By.CLASS_NAME, "doc-link")
                .find_element(By.TAG_NAME, "a")
                .get_attribute("href")
            )
            logger.debug(f"looking through {announcement_title}")
            announcement_date: datetime = datetime.strptime(
                announcement_details[0].text, "%d/%m/%Y %H:%M"
            ).replace(tzinfo=HONG_KONG_TIME)

            news_info = parse_announcement(
                keywords=keywords,
                search_str=f"{announcement_title}{announcement_stock_name}",
                announcement_link = announcement_link,
                announcement_date=announcement_date,
                announcement_title=announcement_title,
                tally=tally
            )
            if news_info is None:
                break
        log_run_results("HKX", tally=tally)
    finally:
        driver.quit()

def scrape_sgx(sheet_dict: dict[str, list[str]]) -> None:
    keywords: list[str] = sheet_dict["keywords"]
    page_num: int = 1
    last_page: bool = False
    driver = Driver(uc=True, headless=True)
    tally = RunTally()
    try:
        while not last_page:
            scrape_link: str = f"https://www.sgx.com/securities/company-announcements?page={page_num}&pagesize=200"
            logger.info(f"Starting scrape for {scrape_link}")
            driver.get(scrape_link)
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tbody > tr > td"))
            )
            logger.info(f"Retrieving announcements for {scrape_link}")
            announcements: list[WebElement] = driver.find_elements(
                By.CSS_SELECTOR, "tbody > tr"
            )

            logger.info(f"Found {len(announcements)} announcements, parsing...")
            for announcement in announcements:
                announcement_data: list[WebElement] = announcement.find_elements(
                    By.TAG_NAME, "td"
                )
                announcement_date: datetime = datetime.strptime(
                    announcement_data[0].text, "%d %b %Y %H:%M %p"
                ).replace(tzinfo=SINGAPORE_TIME)
                issuer_name: str = announcement_data[1].text
                security_name: str = announcement_data[2].text
                announcement_title: str = announcement_data[3].text
                logger.debug(f"Looking through {announcement_title}{issuer_name}{security_name}")
                announcement_link: str = (
                    announcement_data[3]
                    .find_element(By.TAG_NAME, "a")
                    .get_attribute("href")
                )

                news_info = parse_announcement(
                    keywords=keywords,
                    search_str=f"{announcement_title}{issuer_name}{security_name}",
                    announcement_link=announcement_link,
                    announcement_date=announcement_date,
                    announcement_title=announcement_title,
                    tally=tally
                )
                if news_info is None:
                    last_page = True
                    break
            if not last_page:
                logger.info(
                    f"Not at end of relevant announcements for SGX after {tally.total_count} docs scraped, going to next page."
                )
                page_num += 1
        log_run_results("SGX", tally=tally)
    finally:
        driver.quit()

def scrape_bursa_my(sheet_dict: dict[str, list[str]]) -> None:
    ## Use their API, you can probably access it.
    keywords: list[str] = sheet_dict["keywords"]
    current_time: int = int(datetime.now(GMT_PLUS_7).timestamp())
    page_count: int = 0
    last_page: bool = False
    tally = RunTally()
    driver = Driver(uc=True, headless=True)
    try:
        logger.info("Starting scrape for https://www.bursamalaysia.com/")
        while not last_page:
            page_count += 1
            scrape_link: str = f"https://www.bursamalaysia.com/api/v1/announcements/search?ann_type=company&per_page=50&page={page_count}&_={current_time}"
            driver.get(scrape_link)
            announcement_json_str: str = driver.page_source.split("<pre>")[1].split(
                "</pre>"
            )[0]
            announcement_json: dict = loads(announcement_json_str)
            data: list[list[str | int]] = announcement_json["data"]
            for entry in data:
                date_str: str = entry[1].split("d-none'>")[1].split("</div>")[0]
                link_ext: str = entry[3].split("href='")[1].split("' target=")[0]
                announcement_link: str = f"https://bursamalaysia.com{link_ext}"
                company_name: str = (
                    entry[2].split("_blank>")[1].split("</a")[0]
                    if entry[2] != "-"
                    else ""
                )
                announcement_title: str = entry[3].split("_blank>")[1].split("</a")[0]
                announcement_date: datetime = datetime.strptime(
                    date_str, "%d %b %Y"
                ).replace(tzinfo=KUALA_LUMPUR_TIME)

                news_info = parse_announcement(
                    keywords=keywords,
                    search_str=f"{announcement_title}{company_name}",
                    announcement_link=announcement_link,
                    announcement_date=announcement_date,
                    announcement_title=announcement_title,
                    tally=tally
                )
                if news_info is None:
                    last_page = True
                    break
            if not last_page:
                logger.info(
                    f"Not at end of relevant announcements for Malaysia after {tally.total_count} docs scraped, going to next page."
                )
        log_run_results("Bursa MY", tally=tally)
    finally:
        driver.quit()

def scrape_szse(sheet_dict: dict[str, list[str]]) -> None:
    keywords: list[str] = sheet_dict["keywords"]
    stock_codes: list[str] = sheet_dict["stock_code_cn"]
    page_num: int = 1
    last_page: bool = False
    driver = Driver(uc=True, headless=True)
    tally = RunTally()
    scrape_link: str = "https://www.szse.cn/disclosure/listed/notice/index.html"
    logger.info(f"Starting scrape for {scrape_link}")
    try:
        driver.get(scrape_link)
        while not last_page:
            logger.info(f"SZSE page {page_num} scraping...")
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".disclosure-tbody > tr > td")
                )
            )
            announcements: list[WebElement] = driver.find_elements(
                By.CSS_SELECTOR, ".disclosure-tbody > tr"
            )

            for announcement in announcements:
                announcement_details: list[WebElement] = announcement.find_elements(
                    By.TAG_NAME, "td"
                )
                announcement_stock_code: str = (
                    announcement_details[0].find_element(By.TAG_NAME, "a").text
                )
                announcement_stock_name: str = (
                    announcement_details[1].find_element(By.TAG_NAME, "a").text
                )
                announcement_files: list[WebElement] = announcement_details[
                    2
                ].find_elements(By.TAG_NAME, "a")
                date_text: str = (
                    announcement_details[3].find_elements(By.TAG_NAME, "span")[0].text
                )
                # This date extraction is because the Shenzhen stock exchange for some reason uses *TWO* datetime formats.
                announcement_date: datetime = datetime.strptime(
                    date_text.split(" ", maxsplit=1)[0], "%Y-%m-%d"
                ).replace(tzinfo=SHENZHEN_TIME)
                relevant_stock_codes: list[str] = [
                    stock_code
                    for stock_code in stock_codes
                    if stock_code == announcement_stock_code
                ]
                for file in announcement_files:
                    announcement_title: str = file.get_attribute("data-title")
                    announcement_link: str = file.get_attribute("href")
                    parse_announcement(
                        keywords=keywords + relevant_stock_codes,
                        search_str=f"{announcement_title}{announcement_stock_code}{announcement_stock_name}",
                        announcement_link=announcement_link,
                        announcement_date=announcement_date,
                        announcement_title=announcement_title,
                        tally=tally
                    )
                    logger.debug(
                        f"{announcement_stock_code} {announcement_title} {announcement_link}"
                    )
            paginator: WebElement = driver.find_element(By.ID, "paginator")
            this_page: WebElement = paginator.find_element(
                By.CSS_SELECTOR, f'a[data-pi="{page_num - 1}"]'
            )
            if "last" in this_page.get_attribute("class"):
                log_run_results("SZSE", tally=tally)
                break
            logger.info(
                f"Not at end of relevant announcements for SZSE after {tally.total_count} docs scraped, going to next page."
            )
            page_num += 1
            paginator.find_element(By.CSS_SELECTOR, ".next > a").click()
            WebDriverWait(driver, 30).until(EC.staleness_of(announcements[1]))
    finally:
        driver.quit()

def scrape_sse(sheet_dict: dict[str, list[str]]) -> None:
    keywords: list[str] = sheet_dict["keywords"]
    stock_codes: list[str] = sheet_dict["stock_code_cn"]
    tally = RunTally()
    page_num: int = 0
    last_page: bool = False
    driver = Driver(
        uc=True,
        headless=True,
        page_load_strategy="eager",
    )
    driver.set_page_load_timeout(45)
    try:
        scrape_link: str = "https://www.sse.com.cn/disclosure/listedinfo/announcement/"
        logger.info(f"Starting scrape for {scrape_link}")
        driver.get(scrape_link)
        logger.info("Waiting for page to fully load...")
        WebDriverWait(driver, 120).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tbody > tr > td"))
        )
        table_entry: WebElement = driver.find_element(By.CSS_SELECTOR, "tbody > tr > td")
        logger.info("Clicking button to get last three days of info...")
        date_range_button: WebElement = driver.find_element(By.CLASS_NAME, "range_date")
        click_try: int = 0
        while click_try < max_tries:
            try:
                click_try += 1
                logger.debug(f"Clicking annoying button attempt {click_try}")
                date_range_button.click()
                WebDriverWait(driver, 1).until(
                    EC.presence_of_element_located(
                        (By.CLASS_NAME, "laydate-btns-latestThree")
                    )
                )
                break
            except WebDriverException:
                pass
        three_day_button: WebElement = driver.find_element(
            By.CLASS_NAME, "laydate-btns-latestThree"
        )
        three_day_button.click()
        WebDriverWait(driver, 30).until(EC.staleness_of(table_entry))
        while not last_page:
            page_num += 1
            logger.info(f"SSE page {page_num} scraping...")
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tbody > tr > td"))
            )
            announcements: list[WebElement] = driver.find_elements(
                By.CSS_SELECTOR, "tbody > tr"
            )
            announcement_stock_name: str = "N/A"
            announcement_stock_code: str = "N/A"
            for announcement in announcements:
                ann_class: str = announcement.get_attribute("class")
                announcement_details: list[WebElement] = announcement.find_elements(
                    By.TAG_NAME, "td"
                )
                announcement_link: str = (
                    announcement_details[2]
                    .find_element(By.TAG_NAME, "a")
                    .get_attribute("href")
                )
                date_text: str = announcement_details[5].text
                announcement_date: datetime = datetime.strptime(
                    date_text, "%Y-%m-%d"
                ).replace(tzinfo=SHANGHAI_TIME)
                if ann_class == "multiple_bag" or "last_multiple" in ann_class:
                    pass
                else:
                    announcement_stock_code: str = (
                        announcement_details[0].find_element(By.TAG_NAME, "a").text
                    )
                    announcement_stock_name: str = (
                        announcement_details[1].find_element(By.TAG_NAME, "a").text
                    )
                announcement_title: str = (
                    announcement_details[2].find_element(By.TAG_NAME, "a").text
                )
                relevant_stock_codes: list[str] = [
                    stock_code
                    for stock_code in stock_codes
                    if stock_code == announcement_stock_code
                ]
                news_info = parse_announcement(
                    keywords=keywords + relevant_stock_codes,
                    search_str=f"{announcement_title}{announcement_stock_code}{announcement_stock_name}",
                    announcement_link=announcement_link,
                    announcement_date=announcement_date,
                    announcement_title=announcement_title,
                    tally=tally
                )
                logger.debug(f"{announcement_title}")
                if "last_multiple" in ann_class:
                    announcement_stock_name: str = "N/A"
                    announcement_stock_code: str = "N/A"
                if news_info is None:
                    last_page = True
                    break
            if not last_page:
                logger.info(
                    f"Not at end of relevant announcements for SSE after {tally.total_count} docs scraped, going to next page."
                )
                next_button: WebElement = driver.find_element(
                    By.CLASS_NAME, "next"
                ).find_element(By.TAG_NAME, "a")
                next_button.click()
                WebDriverWait(driver, 30).until(EC.staleness_of(announcements[0]))
            else:
                log_run_results("SSE", tally=tally)
    finally:
        driver.quit()

def scrape_sgx_json(sheet_dict: dict[str, list[str]]) -> None:
    timezone_fmt = "%Y%m%d_%H%M%S"
    sgt = timezone(timedelta(hours=8))
    keywords: list[str] = sheet_dict["keywords"]

    def get_sgx_token() -> str:
        req_params = {
            "queryId": "9c3e9f7f03300303a53a580b5a7e760732e5a320:we_chat_qr_validator"
        }
        request = get(
            url="https://api2.sgx.com/content-api/",
            params=req_params
        )
        request.raise_for_status()
        return codecs.decode(request.json()["data"]["qrValidator"], "rot13")

    def _add_years(dt: datetime, years: int) -> datetime:
        """moment().add(n, 'Y'): same month/day, clamped to month end (Feb 29 -> Feb 28)."""
        y = dt.year + years
        day = min(dt.day, calendar.monthrange(y, dt.month)[1])
        return dt.replace(year=y, day=day)

    def _start_of_day(dt: datetime) -> datetime:
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    def _end_of_day(dt: datetime) -> datetime:
        return dt.replace(hour=23, minute=59, second=59, microsecond=999000)

    def sgx_default_period(
            now: datetime | None = None,
            years_back: int = 20,
            local_tz: timezone = sgt
    ) -> dict:
        """Return {'periodstart': ..., 'periodend': ...} exactly as the site's JS would.

        `now` should be timezone-aware; default is the current time in `local_tz`.
        `local_tz` must be the zone the *browser* would be in (the JS uses local day
        boundaries, then converts to UTC).
        """
        now = (now or datetime.now(local_tz)).astimezone(local_tz)

        # --- from: now - N years, start of local day, converted to UTC ---
        start = _start_of_day(_add_years(now, -years_back)).astimezone(UTC)

        # JS floor clamp: if from <= startOf('year') - N years (startOf day), from = that floor.
        # Quirk: the floor is a LOCAL-mode moment, so on that branch it is formatted in LOCAL
        # time, not UTC. Only reachable on 1 Jan (local); not seen in the HARs.
        floor = _start_of_day(_add_years(now.replace(month=1, day=1), -years_back))
        start_str = (floor if start <= floor.astimezone(UTC) else start).strftime(timezone_fmt)

        # --- to: end of local day (23:59:59.999), converted to UTC; ms dropped by format ---
        end_str = _end_of_day(now).astimezone(UTC).strftime(timezone_fmt)

        return {"periodstart": start_str, "periodend": end_str}

    def get_sgx_announcements(
            start: int,
            size: int
    ) -> dict:
        # noinspection PyArgumentList
        session = cffi_requests.Session(impersonate="chrome")
        headers = {
            "Origin": "https://www.sgx.com",
            "Referer": "https://www.sgx.com/",
        }
        period_dict = sgx_default_period()
        req_params = {
            "periodstart": period_dict["periodstart"],
            "periodend": period_dict["periodend"],
            "pagestart": start,
            "pagesize": size,
        }

        token = get_sgx_token()
        request = session.get(
            url="https://api.sgx.com/announcements/v1.1/",
            params=req_params,
            headers={**headers, "Authorizationtoken": token}
        )
        logger.info(f"Sent request to {request.url}")
        logger.info(f"Headers sent: {request.request.headers}")
        if request.status_code in (401, 403):
            logger.info("Authentication to announcement endpoint rejected, retrying.")
            return get_sgx_announcements(start, size)
        request.raise_for_status()
        return request.json()

    page_start: int = 0
    page_size: int = 200
    last_page: bool = False
    tally: RunTally = RunTally()
    logger.info("Starting scrape for SGX via JSON API.")
    while not last_page:
        logger.info("Retrieving announcements...")
        announcement_data = get_sgx_announcements(
            start=page_start,
            size=page_size
        )
        logger.info("JSON retrieved.")
        for announcement in announcement_data["data"]:
            announcement_date = datetime.fromtimestamp(
                announcement["broadcast_date_time"]/1000,
                tz=UTC
            )
            title = announcement["title"]
            issuer_name = announcement["issuer_name"]
            security_name = announcement["security_name"]
            announcement_link = announcement["url"]
            announcement_title = announcement["title"]
            news_info = parse_announcement(
                keywords=keywords,
                search_str=f"{title}{issuer_name}{security_name}",
                announcement_link=announcement_link,
                announcement_date=announcement_date,
                announcement_title=announcement_title,
                tally=tally
            )
            if news_info is None:
                last_page = True
                break
        if not last_page:
            logger.info(
                f"Not at end of relevant announcements for SGX after {tally.total_count} docs scraped, going to next page."
            )
        page_start += 1
    log_run_results("SGX", tally=tally)
