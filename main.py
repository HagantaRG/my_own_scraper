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
from threading import Thread, Event
from csv import DictReader

# Third party libs
from selenium.common.exceptions import WebDriverException

# Custom libs
from gmail_client import GoogleClient
import email_client
import scrapers
from utils.filepaths import LOGS_FOLDER, SETTINGS_FOLDER
from utils.toml_reader import Toml
from utils import email_utils, toml_reader
from utils.scraper_utils import write_run_error_to_csv, write_run_to_csv
from schedule import every, run_pending, clear

"""
This should be the main thing that orchestrates all the scrapers and various other tasks. 
"""

log_file: str = f"{LOGS_FOLDER}/scraper.log"
makedirs(f"{LOGS_FOLDER}", exist_ok=True)
logging.basicConfig(
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(filename=log_file, encoding='utf-8'),
    ],
    level=logging.INFO,
    format="[%(asctime)s] - %(filename)s:%(lineno)s - %(funcName)10s() - %(levelname)s - %(message)s ",
    datefmt='%m/%d/%Y %I:%M:%S %p',
)

def run_scrape_job(
        job: Callable,
        job_name: str,
        start_time: datetime,
        sheet_dict: dict[str, list[str]],
        mail_settings: dict[str, str | list]
) -> None:
    tries: int = 0
    exc: Exception = Exception()
    while tries < 5:
        try:
            tries += 1
            logging.info(f"Running {job_name}, attempt {tries}")
            job(sheet_dict)
            end_time: datetime = datetime.now()
            scrape_time: timedelta = end_time - start_time
            logging.info(f"{job_name} scrape completed! Took {scrape_time.total_seconds()} seconds")
            write_run_to_csv(
                job_name=job_name,
                start_time=start_time,
                end_time=end_time,
                duration=scrape_time,
            )
            return None
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
            exc = exception
        except Exception as exception:
            # N.B. this generic retry is here because if there is an issue with the HTML of the page,
            # e.g. if the page that is loaded has 1 less element than normal somewhere, it would cause a generic error.
            # and I have no real way of differentiating it.
            logging.error(exception)
            logging.error(traceback.format_exception(exception))
            logging.error(
                f"Generic error encountered during scrape job, retrying."
            )
    else:
        logging.error(f"{job_name} scrape attempted {tries} times, ending attempts. Emailing admin.")
        email_client.send_email(
            subject=f"Repeated failure of {job_name}",
            body=f"{traceback.format_exception(exc)} \n {exc}",
            sender=mail_settings["sender"],
            recipients=mail_settings["admin"],
            password=mail_settings["password"],
        )
        return None

def retrieve_keywords_csv(
        google_client: GoogleClient,
        sheet_id: str
) -> dict[str,list[str]]:
    # This is also really ugly, please find a real home for it.
    # This will need to be changed for each
    # Retrieve keywords csv
    logging.info("Retrieving keywords CSV.")
    sheet_paths: list[Path] = google_client.get_spreadsheet_as_csv(sheet_id, "temp", "keywords")
    logging.info("Retrieved CSV.")
    sheet_dict: dict[str, list[str]] = {}
    with open(sheet_paths[0], "r", encoding='utf-8') as csv_file:
        csv_reader: DictReader = DictReader(csv_file, delimiter=",")
        for field in csv_reader.fieldnames:
            sheet_dict[field] = []
        for row in csv_reader:
            for field in csv_reader.fieldnames:
                if row[field] == '':
                    continue
                else:
                    sheet_dict[field].append(str(row[field]).upper())
    logging.info(f"Keywords: {sheet_dict}")
    return sheet_dict


def scrape_orchestrator(
        test_mode: bool = False,
        target_site: str = ...
) -> None:
    google_client: GoogleClient = GoogleClient(f"{SETTINGS_FOLDER}/service_credentials.json")

    # Load settings, in case any changes since last run
    settings_toml: toml_reader.Toml = Toml(Path(f"{SETTINGS_FOLDER}/settings.toml"))
    logging.info(f"Loaded settings from {SETTINGS_FOLDER}/settings.toml")
    email_settings: dict[str, str | list] = settings_toml.load("email-settings")
    keyword_settings: dict[str, str | list] = settings_toml.load("keyword-document")
    sheet_id: str = keyword_settings["sheet-id"]
    sheet_dict: dict[str, list[str]] = retrieve_keywords_csv(google_client, sheet_id)

    # Loop through scraping functions and run, logging successes vs failures
    for a in dir(scrapers):
        item = getattr(scrapers, a)
        if callable(item) and a.startswith("scrape_") and target_site is ...:
            start_time: datetime = datetime.now()
            run_scrape_job(
                job=item,
                job_name=a.title(),
                start_time=start_time,
                sheet_dict=sheet_dict,
                mail_settings=email_settings
            )
        elif target_site is not ... and target_site in a.title().lower():
            logging.info(f"Running scrape for {target_site} website.")
            start_time: datetime = datetime.now()
            run_scrape_job(
                job=item,
                job_name=a.title(),
                start_time=start_time,
                sheet_dict=sheet_dict,
                mail_settings=email_settings
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
                recipients=email_settings["recipients"] if not test_mode else email_settings["admin"],
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
    if test_mode:
        logging.info(f"Test run carried out without unhandled errors.")
    return None

def run_threaded(
        job_func: Callable,
        *args,
        **kwargs
):
    job_thread = Thread(target=job_func, args=args, kwargs=kwargs, daemon=True)
    job_thread.start()

def run_continuously(interval=1):
    """Continuously run, while executing pending jobs at each
    elapsed time interval.
    @return cease_continuous_run: threading. Event which can
    be set to cease continuous run. Please note that it is
    *intended behavior that run_continuously() does not run
    missed jobs*. For example, if you've registered a job that
    should run every minute, and you set a continuous run
    interval of one hour then your job won't be run 60 times
    at each interval but only once.
    """
    stopper_event = Event()
    class ScheduleThread(Thread):
        @classmethod
        def run(cls):
            while not stopper_event.is_set():
                run_pending()
                sleep(interval)

    background_scheduler = ScheduleThread(daemon=True)
    background_scheduler.start()
    logging.info("Background scheduler started.")
    return stopper_event

stop_event: Event = Event()
try:
    while True:
        user_input: str = input(f"Awaiting user input for scraper. Please enter \"help\" to get a list of valid commands.\n")
        match user_input:
            case "help":
                print(
                    f"Available commands:\n"
                    f"test-run: Carries out a one-off run of the *whole* scraper, emailing only the admins.\n"
                    f"standard-schedule: Standard scheduled scraper, running at 9:00 AM local time every day.\n"
                    f"single-scrape: Runs the scraper once. Does not schedule anything.\n"
                    f"single-site: Scrapes one of the supported websites. Available codes will be displayed on selection."
                )
            case "test-run":
                run_threaded(
                    scrape_orchestrator,
                    test_mode=True
                )
            case "standard-schedule":
                # The way this works is that there is one long-running thread that exists for the scheduler
                # and *that* thread will spin up another daemon thread for the daily scrape jobs.
                clear()
                stop_event.set()
                logging.info("Cleared any existing jobs, cleared previously existing schedulers.")
                main_schedule = every().day.at("09:00").do(
                    run_threaded,
                    scrape_orchestrator
                )
                logging.info("9AM scrapes scheduled.")
                stop_event: Event = run_continuously()
            case "single-scrape":
                run_threaded(
                    scrape_orchestrator
                )
            case "single-site":
                site_code: str = input(
                    "bursa_my: The Malaysian stock exchange website.\n"
                    "szse: The Shenzhen stock exchange website.\n"
                    "sse: The Shanghai stock exchange website.\n"
                    "sgx: The Singaporean stock exchange website.\n"
                    "hkx: The Hong Kong stock exchange website.\n"
                )
                site_list: list[str] = ["bursa_my", "szse", "sgx", "hkx", "sse"]
                if site_code not in site_list:
                    print(f"Invalid site code.")
                else:
                    run_threaded(
                        scrape_orchestrator,
                        test_mode=True,
                        target_site=site_code
                    )
            case _:
                print("Invalid command.")
        sleep(2)

except KeyboardInterrupt:
    stop_event.set()
    print("Program execution stopped. Cleared schedulers.")


