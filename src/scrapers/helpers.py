import csv
import logging
from collections import Counter
from datetime import datetime, timedelta
from os import makedirs, path

from filelock import FileLock

from src.utils.constants import GMT_PLUS_7
from src.utils.filepaths import DATA_FOLDER
from src.utils.news_utils import NewsInformation

logger = logging.getLogger(__name__)
NEWS_DATA_PATH = f"{DATA_FOLDER}/news_data.csv"
NEWS_DATA_LOCK_PATH = f"{NEWS_DATA_PATH}.lock"
NEWS_DATA_HEADERS: list[str] = ["link", "title", "date", "keywords", "retrieved_at"]
RUN_DATA_HEADERS: list[str] = [
    "job_name",
    "start_time",
    "end_time",
    "duration",
    "success",
    "error_message",
]

class RunTally(Counter):
    TOTAL = "total"
    RELEVANT = "relevant"
    _ALLOWED = {TOTAL, RELEVANT}  # noqa: RUF012

    def __init__(self) -> None:
        super().__init__(total=0, relevant=0)

    def __setitem__(self, key: str, value: int) -> None:
        if key not in self._ALLOWED:
            raise KeyError(f"Unknown tally key: {key!r}")
        super().__setitem__(key, value)

    def __missing__(self, key: str) -> int:
        raise KeyError(key)

def check_link_parsed_csv(news: NewsInformation) -> bool:
    if not path.isfile(NEWS_DATA_PATH):
        return False
    with open(
        NEWS_DATA_PATH,
        newline="",
        encoding="utf-8"
    ) as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=NEWS_DATA_HEADERS)
        for row in reader:
            if row["link"] == news.news_link and row["title"] == news.news_title:
                return True
    return False

def write_info_to_csv(info: NewsInformation) -> None:
    makedirs(f"{DATA_FOLDER}", exist_ok=True)
    with FileLock(NEWS_DATA_LOCK_PATH), open(
        NEWS_DATA_PATH,
        "a",
        newline="",
        encoding="utf-8"
    ) as csvfile:
        writer = csv.DictWriter(csvfile, delimiter=",", fieldnames=NEWS_DATA_HEADERS)
        keyword_string: str = ""

        if info.relevant_keywords:
            for keyword in info.relevant_keywords[0:-1]:
                keyword_string += f"{keyword},"
            keyword_string += f"{info.relevant_keywords[-1]}"

        if not check_link_parsed_csv(info):
            writer.writerow(
                {
                    "link": info.news_link,
                    "title": info.news_title,
                    "date": info.news_date,
                    "keywords": keyword_string,
                    "retrieved_at": info.retrieved_at,
                }
            )
        else:
            logger.info(f"Link {info.news_link} already in CSV, not writing.")

def check_run_done(news: NewsInformation) -> bool:
    if datetime.now(GMT_PLUS_7) > news.news_date + timedelta(days=1, hours=12):
        logger.info(
            "Announcement older than 1 day, 12 hours. Done looking through latest announcements, scrape finished."
        )
        return True
    if check_link_parsed_csv(news):
        logger.info(
            f"Reached an already-parsed announcement at {news.news_link} Done looking through latest announcements, scrape finished."
        )
        return True
    return False

def log_run_results(
        scrape_name: str,
        tally: RunTally
) -> None:
    logger.info(
        f"Done scraping {scrape_name}, "
        f"scraped total of {tally[RunTally.TOTAL]} announcements."
        f" Found {tally[RunTally.RELEVANT]} relevant announcements."
    )

def parse_announcement(  # noqa: PLR0913, PLR0917
        search_str: str,
        keywords: list[str],
        announcement_link: str,
        announcement_date: datetime,
        announcement_title: str,
        tally: RunTally
) -> NewsInformation | None:
    relevant_keywords: list[str] = [
        keyword
        for keyword in keywords
        if keyword in search_str.upper()
    ]

    news_info: NewsInformation = NewsInformation(
        news_link=announcement_link,
        news_date=announcement_date,
        news_title=announcement_title,
        retrieved_at=datetime.now(GMT_PLUS_7),
        relevant_keywords=relevant_keywords if len(relevant_keywords) > 0 else None,
    )

    if check_run_done(news_info):
        return None

    if news_info.relevant_keywords is not None:
        write_info_to_csv(news_info)
        tally[RunTally.RELEVANT] += 1
    tally[RunTally.TOTAL] += 1
    return news_info
