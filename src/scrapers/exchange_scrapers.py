import calendar
import codecs
import logging
from datetime import UTC, datetime, timedelta, tzinfo

from curl_cffi import requests as cffi_requests
from curl_cffi.requests.exceptions import RequestException

from src.scrapers.helpers import (
    RunTally,
    log_run_results,
    parse_announcement,
)
from src.scrapers.scrape_errors import UnexpectedPageFormatError
from src.utils.constants import (
    CHINA_TIME,
    GMT_PLUS_7,
    HONG_KONG_TIME,
    KUALA_LUMPUR_TIME,
    SINGAPORE_TIME,
)

logger = logging.getLogger(__name__)

def scrape_bursa_my_json(sheet_dict: dict[str, list[str]]) -> None:
    ## Use their API, you can probably access it.
    keywords: list[str] = sheet_dict["keywords"]
    current_time: int = int(datetime.now(GMT_PLUS_7).timestamp())
    page_count: int = 0
    last_page: bool = False
    tally: RunTally = RunTally()
    # noinspection PyArgumentList
    session = cffi_requests.Session(impersonate="chrome")
    logger.info("Starting scrape for https://www.bursamalaysia.com/")
    while not last_page:
        page_count += 1
        params: dict [str, str|int] = {
            "ann_type": "company",
            "per_page": "50",
            "page": page_count,
            "_": current_time
        }
        scrape_link: str = "https://www.bursamalaysia.com/api/v1/announcements/search"
        response = session.get(
            url=scrape_link,
            params=params,
        )
        response.raise_for_status()
        data: list[list[str | int]] = response.json()["data"]
        if not data:
            break
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
                f"Not at end of relevant announcements for Malaysia after {tally[RunTally.TOTAL]} docs scraped, going to next page."
            )
    log_run_results("Bursa MY", tally=tally)

def scrape_sgx_json(sheet_dict: dict[str, list[str]]) -> None:
    timezone_fmt = "%Y%m%d_%H%M%S"
    keywords: list[str] = sheet_dict["keywords"]
    # noinspection PyArgumentList
    session = cffi_requests.Session(impersonate="chrome")

    def get_sgx_token() -> str:
        req_params = {
            "queryId": "9c3e9f7f03300303a53a580b5a7e760732e5a320:we_chat_qr_validator"
        }
        response = session.get(
            url="https://api2.sgx.com/content-api/",
            params=req_params
        )
        response.raise_for_status()
        return codecs.decode(response.json()["data"]["qrValidator"], "rot13")

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
            local_tz: tzinfo = SINGAPORE_TIME
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
        response = session.get(
            url="https://api.sgx.com/announcements/v1.1/",
            params=req_params,
            headers={**headers, "Authorizationtoken": token}
        )
        logger.info(f"Sent request to {response.url}")
        response.raise_for_status()
        return response.json()

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
        data = announcement_data["data"]
        if not data:
            break
        for announcement in data:
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
                f"Not at end of relevant announcements for SGX after {tally[RunTally.TOTAL]} docs scraped, going to next page."
            )
        page_start += 1
    log_run_results("SGX", tally=tally)

def scrape_sse_json(sheet_dict: dict[str, list[str]]) -> None:
    tally: RunTally = RunTally()
    stock_codes: list[str] = sheet_dict["stock_code_cn"]
    keywords: list[str] = sheet_dict["keywords"]
    base_url: str = "https://static.sse.com.cn"
    date_format = "%Y-%m-%d"
    url = "https://query.sse.com.cn/security/stock/queryCompanyBulletinNew.do"
    # noinspection PyArgumentList
    session = cffi_requests.Session(impersonate="chrome")
    start_date = (datetime.now(tz=CHINA_TIME) - timedelta(days=2)).strftime(date_format)
    end_date = (datetime.now(tz=CHINA_TIME) + timedelta(days=2)).strftime(date_format)
    current_page: int = 0
    last_page: bool = False
    sse_headers = {
        "Referer": "https://static.sse.com.cn/",  # required.
    }
    logger.info(f"Starting scrape for {url}")
    while not last_page:
        current_page += 1
        sse_params = {
            "isPagination": "true",
            "pageHelp.pageSize": 25,  # This is clamped @ 25 by the server
            "pageHelp.pageNo": current_page,  # keep pageNo/beginPage/endPage equal
            "pageHelp.beginPage": current_page, # N.B. this is the ONLY param that matters for pagination.
            "pageHelp.endPage": current_page,
            "pageHelp.cacheSize": 1,
            "START_DATE": start_date,  # YYYY-MM-DD; future dates tolerated
            "END_DATE": end_date,
            "SECURITY_CODE": "",  # e.g. "600115" to filter one stock
            "TITLE": "",
            "BULLETIN_TYPE": "",
            "stockType": "",
        }
        response = session.get(
            url=url,
            headers=sse_headers,
            params=sse_params
        )
        response.raise_for_status()
        response_json = response.json()
        if "pageHelp" not in response_json:
            raise RequestException("Request was denied.", response_json)
        result = response_json["result"]
        if result and not isinstance(result[0], list):
            raise UnexpectedPageFormatError("SSE result shape changed: expected list-of-lists")
        for group in result:
            for announcement in group:
                announcement_stock_code: str = announcement["SECURITY_CODE"]
                announcement_title: str = announcement["TITLE"]
                announcement_stock_name: str = announcement["SECURITY_NAME"]
                announcement_link: str = f"{base_url}{announcement["URL"]}"
                announcement_date: datetime = datetime.strptime(
                    announcement["SSEDATE"],
                    date_format
                ).replace(tzinfo=CHINA_TIME)
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
                    tally=tally,
                    cutoff=timedelta(days=2)
                )
                if news_info is None:
                    last_page = True
                    break
            if last_page:
                break
        if response_json["pageHelp"]["pageCount"] <= current_page:
            break
        if not last_page:
            logger.info(
                f"Not at end of relevant announcements for SSE after {tally[RunTally.TOTAL]} docs scraped, going to next page."
            )
    log_run_results("SSE", tally=tally)

def scrape_hkx_json(sheet_dict: dict[str, list[str]]) -> None:
    keywords: list[str] = sheet_dict["keywords"]
    tally: RunTally = RunTally()
    announcements: list = []
    base_url: str = "https://www1.hkexnews.hk/listedco/listconews/sehk"
    date_format: str = "%d/%m/%Y %H:%M"
    # noinspection PyArgumentList
    session = cffi_requests.Session(impersonate="chrome")
    for num in range(1,3):
        url: str = f"https://www1.hkexnews.hk/ncms/json/eds/lcisehk1relsde_{num}.json"
        response = session.get(url)
        response.raise_for_status()
        announcements += response.json()["newsInfoLst"]
    for announcement in announcements:
        announcement_title: str = announcement["title"]
        announcement_stock_code: str = announcement["stock"][0]["sc"]
        announcement_stock_name: str = announcement["stock"][0]["sn"]
        announcement_link: str = f"{base_url}{announcement["webPath"]}"
        announcement_date: datetime = datetime.strptime(
            announcement["relTime"],
            date_format
        ).replace(tzinfo=CHINA_TIME)
        news_info = parse_announcement(
            keywords=keywords,
            search_str=f"{announcement_title}{announcement_stock_code}{announcement_stock_name}",
            announcement_link=announcement_link,
            announcement_date=announcement_date,
            announcement_title=announcement_title,
            tally=tally,
            cutoff=timedelta(days=2)
        )
        if news_info is None:
            break
    log_run_results("HKX", tally=tally)

def scrape_szse_json(sheet_dict: dict[str, list[str]]) -> None:
    keywords: list[str] = sheet_dict["keywords"]
    stock_codes: list[str] = sheet_dict["stock_code_cn"]
    date_format: str = "%Y-%m-%d %H:%M:%S"
    end_date: datetime = datetime.now(tz=CHINA_TIME)
    start_date: datetime = end_date - timedelta(days=7)
    page_num: int = 0
    last_page: bool = False
    # noinspection PyArgumentList
    session = cffi_requests.Session(impersonate="chrome")
    tally: RunTally = RunTally()
    scrape_link: str = "https://www.szse.cn/api/disc/announcement/annList"
    base_url: str = "https://www.szse.cn/disclosure/listed/bulletinDetail/index.html?"
    logger.info(f"Starting scrape for {scrape_link}")
    while not last_page:
        page_num += 1
        payload: dict = {
            "channelCode": ["listedNotice_disc"],
            "pageNum": page_num,
            "pageSize": 100,
            "seDate": [
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d")
            ]
        }
        response = session.post(
            scrape_link,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()["data"]
        if not data:
            break
        for announcement in data:
            announcement_stock_code: str = announcement["secCode"][0]
            announcement_stock_name: str = announcement["secName"][0]
            announcement_title: str = announcement["title"]
            announcement_date: datetime = datetime.strptime(
                announcement["publishTime"],
                date_format
            ).replace(tzinfo=CHINA_TIME)
            announcement_link: str = f"{base_url}{announcement["id"]}"
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
                tally=tally,
                cutoff=timedelta(days=2)
            )
            if news_info is None:
                last_page = True
                break
        if not last_page:
            logger.info(
                f"Not at end of relevant announcements for SZSE after {tally[RunTally.TOTAL]} docs scraped, going to next page."
            )
    log_run_results("SZSE", tally=tally)