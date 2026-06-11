# Python libs
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
import traceback
from collections.abc import Callable
from time import sleep
from smtplib import SMTPException
import shutil
from os import makedirs

# Third party libs
from selenium.common.exceptions import WebDriverException

# Custom libs
from gmail_client import GmailClient
import email_client
import scrapers
from utils.filepaths import LOGS_FOLDER, SETTINGS_FOLDER
from utils.toml_reader import Toml
from utils import email_utils, toml_reader
from utils.scraper_utils import write_run_error_to_csv, write_run_to_csv
from schedule import every, run_pending

"""
This should be the main thing that orchestrates all the scrapers and various other tasks.
Functionality:
- Concurrently run scrape jobs -- for now we can single thread it and pretend this isn't a godawful way to do smth.
- Log success/failures of scrape jobs
"""

log_file: str = f"{LOGS_FOLDER}/scraper.log"
makedirs(f"{LOGS_FOLDER}", exist_ok=True)
logging.basicConfig(
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file),
    ],
    level=logging.INFO,
    format="[%(asctime)s] - %(name)s - %(levelname)s - %(message)s",
    datefmt='%m/%d/%Y %I:%M:%S %p'
)

def run_scrape_job(
        job: Callable,
        job_name: str,
        start_time: datetime,
        keywords: list[str]
) -> None:
    try:
        job(keywords)
        end_time: datetime = datetime.now()
        scrape_time: timedelta = end_time - start_time
        logging.info(f"{job_name} scrape completed! Took {scrape_time.total_seconds()} seconds")
        write_run_to_csv(
            job_name=job_name,
            start_time=start_time,
            end_time=end_time,
            duration=scrape_time,
        )
    except WebDriverException as exception:
        logging.error(exception)
        logging.error(traceback.format_exception(exception))
        logging.error(
            f"WebDriver error during scrape job {job_name}.\n This likely means the page format"
            f" has changed and code changes are required"
        )
        write_run_error_to_csv(
            job_name=job_name,
            start_time=start_time,
            error_message=f"{exception}\n{traceback.format_exception(exception)}",
        )

def main():
    google_client: GmailClient = GmailClient(f"{SETTINGS_FOLDER}/service_credentials.json")

    # Load settings, in case any changes since last run
    settings_toml: toml_reader.Toml = Toml(Path(f"{SETTINGS_FOLDER}/settings.toml"))
    email_settings: dict[str, str | list] = settings_toml.load("email-settings")
    keyword_settings: dict[str, str | list] = settings_toml.load("keyword-document")
    sheet_id: str = keyword_settings["sheet-id"]

    # Retrieve keywords csv
    logging.info("Retrieving keywords CSV.")
    google_client.get_spreadsheet_as_csv(sheet_id, "temp", "keywords")
    logging.info("Retrieved CSV.")

    # Parse keywords, remove any duplicates.
    # This is bad. Please fix it.
    with open(f"temp/keywords-1.csv", "r") as f:
        keywords: list[str] = f.read().splitlines()
    keywords = [word.upper() for word in keywords]
    keywords = list(set(keywords))
    logging.info(f"Keywords: {keywords}")

    # Loop through scraping functions and run, logging successes vs failures
    for a in dir(scrapers):
        item = getattr(scrapers, a)
        if callable(item) and a.startswith("scrape_"):
            logging.info(f"Running {a.title()}!")
            start_time: datetime = datetime.now()
            run_scrape_job(
                job=item,
                job_name=a.title(),
                start_time=start_time,
                keywords=keywords
            )

    # Delete temp directory post-scrape
    logging.info("Done scraping, deleting temp directory.")
    try:
        shutil.rmtree("temp")
    except OSError as e:
        logging.error("Error: %s - %s." % (e.filename, e.strerror))

    # Done scraping, send notifs.
    subject = f"Relevant articles found for {datetime.today().strftime('%Y-%m-%d')}"
    body = email_utils.construct_email()

    tries: int = 0
    while tries <= 5:
        try:
            tries += 1
            email_client.send_email(
                subject=subject,
                body=body,
                sender=email_settings["sender"],
                recipients=email_settings["recipients"],
                password=email_settings["password"],
            )
            break
        except SMTPException as network_error:
            logging.info(f"Network encountered during email sending try number {tries}, trying up to 5 times.")
            logging.info(network_error)
            sleep(3)
            continue
    if tries >= 5:
        logging.error(f"Error encountered in email sending. Emails have NOT been sent.")

main_schedule = every().day.at("09:00").do(main)
while True:
    run_pending()
    sleep(1)