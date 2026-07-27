import csv
import logging
from os import path, makedirs
from datetime import datetime, timedelta

from src.utils.news_utils import NewsInformation
from src.utils.filepaths import DATA_FOLDER

logger = logging.getLogger(__name__)
news_data_headers: list[str] = ["link", "title", "date", "keywords", "retrieved_at"]
run_data_headers: list[str] = ["job_name", "start_time", "end_time", "duration", "success", "error_message"]

def check_link_parsed_csv(news: NewsInformation) -> bool:
    file_exists: bool = path.isfile(f"{DATA_FOLDER}/news_data.csv")
    if not file_exists:
        return False
    with open(f"{DATA_FOLDER}/news_data.csv", "r", newline="", encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=news_data_headers)
        for row in reader:
            if row["link"] == news.news_link and row["title"] == news.news_title:
                return True
    return False

def write_info_to_csv(info: NewsInformation) -> None:
    filename: str = f"{DATA_FOLDER}/news_data.csv"
    makedirs(f"{DATA_FOLDER}", exist_ok=True)
    with open(f"{DATA_FOLDER}/news_data.csv", "a", newline="", encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, delimiter=",", fieldnames=news_data_headers)
        keyword_string: str = ""

        if len(info.relevant_keywords)>0:
            for keyword in info.relevant_keywords[0:-1]:
                keyword_string += f"{keyword},"
            keyword_string+=f"{info.relevant_keywords[-1]}"

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

def write_run_to_csv(
        job_name: str,
        start_time: datetime,
        end_time: datetime,
        duration: timedelta,
) -> None:
    filename: str = f"{DATA_FOLDER}/run_data.csv"
    makedirs(f"{DATA_FOLDER}", exist_ok=True)
    with open(filename, "a", newline="", encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, delimiter=",", fieldnames=run_data_headers)
        writer.writerow(
            {
                run_data_headers[0]: job_name,
                run_data_headers[1]: start_time,
                run_data_headers[2]: end_time,
                run_data_headers[3]: duration,
                run_data_headers[4]: True,
            }
        )

def write_run_error_to_csv(
        job_name: str,
        start_time: datetime,
        error_message: str
) -> None:
    with open(f"{DATA_FOLDER}/run_data.csv", "a", newline="", encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, delimiter=",", fieldnames=run_data_headers)
        writer.writerow(
            {
                run_data_headers[0]: job_name,
                run_data_headers[1]: start_time,
                run_data_headers[2]: "ERROR",
                run_data_headers[3]: "ERROR",
                run_data_headers[4]: False,
                run_data_headers[5]: error_message
            }
        )

def check_run_done(news: NewsInformation) -> bool:
    if datetime.now() > news.news_date + timedelta(days=1, hours=12):
        logger.info(
            f"Announcement older than 1 day, 12 hours. Done looking through latest announcements, scrape finished.")
        return True
    elif check_link_parsed_csv(news):
        logger.info(
            f"Reached an already-parsed announcement at {news.news_link} Done looking through latest announcements, scrape finished.")
        return True
    else:
        return False