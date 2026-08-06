import csv
import logging
from datetime import datetime, timedelta, timezone
from os import makedirs, path

from filelock import FileLock

from src.utils.filepaths import DATA_FOLDER
from src.utils.news_utils import NewsInformation

logger = logging.getLogger(__name__)
GMT_PLUS_7 = timezone(timedelta(hours=7))
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

        if len(info.relevant_keywords) > 0:
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
