# Python libs
import logging
import shutil
import traceback
from collections.abc import Callable
from csv import DictReader
from datetime import datetime, timedelta
from pathlib import Path

# Third party libs
from selenium.common.exceptions import WebDriverException

# Custom libs
from src.gmail_client import GoogleClient
from src.scrapers import exchange_scrapers as scrapers
from src.scrapers.google_scrape import SearchResult, google_search_scrape
from src.smtp_functions import send_email
from src.utils import email_utils, toml_reader
from src.utils.filepaths import SETTINGS_FOLDER, TEMP_FOLDER
from src.utils.scraper_utils import write_run_error_to_csv, write_run_to_csv
from src.utils.toml_reader import Toml

logger = logging.getLogger(__name__)


class ScrapeOrchestrator:
    keywords_sheet: dict[str, list[str]] = ...
    email_settings: dict[str, str | list] = ...
    google_client: GoogleClient = ...
    keywords_sheet_id: str = ...

    def __init__(self):
        self._retrieve_settings()

    def _retrieve_keywords_csv(
        self,
    ) -> None:
        logger.info("Retrieving keywords CSV.")
        sheet_paths: list[Path] = self.google_client.get_spreadsheet_as_csv(
            spreadsheet_id=self.keywords_sheet_id,
            target_folder=TEMP_FOLDER,
            sheet_name="keywords",
        )
        logger.info("Retrieved CSV.")
        sheet_dict: dict[str, list[str]] = {}
        with open(sheet_paths[0], "r", encoding="utf-8") as csv_file:
            csv_reader: DictReader = DictReader(csv_file, delimiter=",")
            for field in csv_reader.fieldnames:
                sheet_dict[field] = []
            for row in csv_reader:
                for field in csv_reader.fieldnames:
                    if row[field] == "":
                        continue
                    else:
                        sheet_dict[field].append(str(row[field]).upper())
        logger.info(f"Keywords: {sheet_dict}")
        self.keywords_sheet = sheet_dict

    def _retrieve_google_client(self) -> None:
        self.google_client = GoogleClient(f"{SETTINGS_FOLDER}/service_credentials.json")

    def _retrieve_settings(self):
        self._retrieve_google_client()
        # Load settings, in case any changes since last run
        settings_path = Path(SETTINGS_FOLDER) / "settings.toml"
        settings_toml: toml_reader.Toml = Toml(settings_path)
        logger.info(
            "Loading settings from %s (exists=%s)",
            settings_path.resolve(),
            settings_path.exists(),
        )
        self.email_settings = settings_toml.load("email-settings")
        logger.info(
            "Loaded email settings keys: %s; admin present=%s; admin value type=%s",
            list(self.email_settings.keys()),
            "admin" in self.email_settings,
            type(self.email_settings.get("admin")).__name__,
        )
        keyword_settings: dict[str, str | list] = settings_toml.load("keyword-document")
        self.keywords_sheet_id = keyword_settings["sheet-id"]
        self._retrieve_keywords_csv()

    def run_google_scrape(self) -> None:
        tries: int = 0
        exc: Exception = Exception()
        start_time: datetime = datetime.now()
        job_name: str = "GoogleScrape"
        search_results: dict[str, list[SearchResult]] = {}
        while tries < 5:
            try:
                tries += 1
                logger.info(f"Running {job_name}, attempt {tries}")
                search_results = google_search_scrape(sheet_dict=self.keywords_sheet)
                end_time: datetime = datetime.now()
                scrape_time: timedelta = end_time - start_time
                logger.info(
                    f"{job_name} scrape completed! Took {scrape_time.total_seconds()} seconds"
                )
                write_run_to_csv(
                    job_name=job_name,
                    start_time=start_time,
                    end_time=end_time,
                    duration=scrape_time,
                )
                break
            except WebDriverException as exception:
                logger.error(exception)
                logger.error(traceback.format_exception(exception))
                logger.error(
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
                logger.error(exception)
                logger.error(traceback.format_exception(exception))
                logger.error("Generic error encountered during scrape job, retrying.")
        else:
            logger.error(
                f"{job_name} scrape attempted {tries} times, ending attempts. Emailing admin."
            )
            send_email(
                subject=f"Repeated failure of {job_name}",
                body=f"{traceback.format_exception(exc)} \n {exc}",
                sender=self.email_settings["sender"],
                recipients=self.email_settings["admin"],
                password=self.email_settings["password"],
            )
        if search_results != {}:
            search_body: str = email_utils.construct_search_email(
                results=search_results
            )
            search_subject: str = (
                f"Relevant searches found for {datetime.today().strftime('%Y-%m-%d')}"
            )
            send_email(
                subject=search_subject,
                body=search_body,
                sender=self.email_settings["sender"],
                recipients=self.email_settings["recipients"],
                password=self.email_settings["password"],
            )

    def _run_scrape_job(
        self,
        job: Callable,
        job_name: str,
    ) -> None:
        tries: int = 0
        exc: Exception = Exception()
        start_time: datetime = datetime.now()
        while tries < 5:
            try:
                tries += 1
                logger.info(f"Running {job_name}, attempt {tries}")
                job(self.keywords_sheet)
                end_time: datetime = datetime.now()
                scrape_time: timedelta = end_time - start_time
                logger.info(
                    f"{job_name} scrape completed! Took {scrape_time.total_seconds()} seconds"
                )
                write_run_to_csv(
                    job_name=job_name,
                    start_time=start_time,
                    end_time=end_time,
                    duration=scrape_time,
                )
                return
            except WebDriverException as exception:
                logger.error(exception)
                logger.error(traceback.format_exception(exception))
                logger.error(
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
                logger.error(exception)
                logger.error(traceback.format_exception(exception))
                logger.error("Generic error encountered during scrape job, retrying.")
        logger.error(
            f"{job_name} scrape attempted {tries} times, ending attempts. Emailing admin."
        )
        send_email(
            subject=f"Repeated failure of {job_name}",
            body=f"{traceback.format_exception(exc)} \n {exc}",
            sender=self.email_settings["sender"],
            recipients=self.email_settings["admin"],
            password=self.email_settings["password"],
        )
        return

    def orchestrate(self, test_mode: bool = False, target_site: str = ...) -> None:
        self._retrieve_settings()

        # Loop through scraping functions and run, logging successes vs failures
        for a in dir(scrapers):
            item = getattr(scrapers, a)
            if callable(item) and a.startswith("scrape_") and target_site is ...:
                self._run_scrape_job(job=item, job_name=a.title())
            elif target_site is not ... and target_site in a.title().lower():
                logger.info(f"Running scrape for {target_site} website.")
                self._run_scrape_job(
                    job=item,
                    job_name=a.title(),
                )
        # Delete temp directory post-scrape
        logger.info("Done scraping, deleting temp directory.")
        try:
            shutil.rmtree(TEMP_FOLDER)
        except OSError as e:
            logger.error("Error: %s - %s.", e.filename, e.strerror)

        # Done scraping, send notifs.
        subject = f"Relevant articles found for {datetime.today().strftime('%Y-%m-%d')}"
        body = email_utils.construct_webscraper_email()
        send_email(
            subject=subject,
            body=body,
            sender=self.email_settings["sender"],
            recipients=self.email_settings["recipients"]
            if not test_mode
            else self.email_settings["admin"],
            password=self.email_settings["password"],
        )

        self.run_google_scrape()

        if test_mode:
            logger.info("Test run carried out without unhandled errors.")
