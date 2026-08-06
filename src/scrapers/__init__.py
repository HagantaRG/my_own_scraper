# Python libs
import logging
import shutil
import traceback
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from csv import DictReader
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Third party libs
from selenium.common.exceptions import WebDriverException
from urllib3.exceptions import ReadTimeoutError

# Custom libs
from src.gmail_client import GoogleClient
from src.scrapers import exchange_scrapers as scrapers
from src.scrapers.google_scrape import SearchResult, google_search_scrape
from src.smtp_functions import send_email
from src.utils import email_utils, toml_reader
from src.utils.cli_utils import print_cli, print_section
from src.utils.filepaths import PROJECT_FOLDER, SETTINGS_FOLDER
from src.utils.toml_reader import Toml

logger = logging.getLogger(__name__)
GMT_PLUS_7 = timezone(timedelta(hours=7))


class UnexpectedPageFormatError(Exception):
    """Page was loaded, and all element exists, but some retrieved values did not match the expected format."""


class ScrapeBatchError(Exception):
    """Some jobs in a batch of scrapes failed."""


ACCEPTABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    WebDriverException,
    UnexpectedPageFormatError,
    ReadTimeoutError,
)


def _run_with_retries[ResultT](
    *, job_name: str, operation: Callable[[], ResultT], max_tries: int
) -> ResultT:
    if max_tries < 1:
        raise ValueError("max_tries must be at least 1")
    for tries in range(1, max_tries + 1):
        try:
            logger.info(f"Running {job_name}, attempt {tries}")
            print_cli(f"{job_name}: attempt {tries}/{max_tries}", "RUN")
            return operation()
        except (WebDriverException, ReadTimeoutError) as exc:
            logger.exception(
                f"{job_name} attempt {tries}/{max_tries} failed with a {type(exc).__name__} error",
            )
            if tries < max_tries:
                print_cli(f"{job_name} failed; retrying.", "RETRY")
                continue
            raise
        except (KeyError, ValueError, IndexError) as exc:
            logger.exception(
                f"{job_name} attempt {tries}/{max_tries} failed with a {type(exc).__name__} error",
            )
            if tries < max_tries:
                print_cli(f"{job_name} returned unexpected data; retrying.", "RETRY")
                continue
            raise UnexpectedPageFormatError(
                "Retrieved page did not match expected format"
            ) from exc
    raise RuntimeError("Retry loop ended unexpectedly")


def _run_scrape_job(
    job: Callable[[dict[str, list[str]]], None],
    job_name: str,
    keywords_sheet: dict[str, list[str]],
    max_tries: int,
) -> bool:
    start_time: datetime = datetime.now(GMT_PLUS_7)
    _run_with_retries(
        job_name=job_name,
        operation=lambda: job(keywords_sheet),
        max_tries=max_tries,
    )
    end_time: datetime = datetime.now(GMT_PLUS_7)
    scrape_time: timedelta = end_time - start_time
    logger.info(
        f"{job_name} scrape completed! Took {scrape_time.total_seconds()} seconds"
    )
    print_cli(
        f"{job_name} completed in {scrape_time.total_seconds():.1f} seconds.",
        "DONE",
    )
    return True


def _run_google_job(
    job_name: str, keywords_sheet: dict[str, list[str]], max_tries: int
) -> dict[str, list[SearchResult]]:
    start_time: datetime = datetime.now(GMT_PLUS_7)
    search_results = _run_with_retries(
        job_name=job_name,
        operation=lambda: google_search_scrape(keywords_sheet),
        max_tries=max_tries,
    )
    end_time: datetime = datetime.now(GMT_PLUS_7)
    scrape_time: timedelta = end_time - start_time
    logger.info(
        f"{job_name} scrape completed! Took {scrape_time.total_seconds()} seconds"
    )
    print_cli(
        f"{job_name} completed in {scrape_time.total_seconds():.1f} seconds.",
        "DONE",
    )
    return search_results


class ScrapeOrchestrator:
    keywords_sheet: dict[str, list[str]] = ...
    email_settings: dict[str, str | list] = ...
    google_client: GoogleClient = ...
    keywords_sheet_id: str = ...
    max_tries: int
    temp_folder: Path

    def __init__(
        self,
        max_tries: int = 5,
    ):
        self.max_tries = max_tries

    def _retrieve_keywords_csv(self, temp_path: Path) -> None:
        logger.info("Retrieving keywords CSV.")
        print_cli("Downloading the latest keyword list.", "SETUP")
        sheet_paths: list[Path] = self.google_client.get_spreadsheet_as_csv(
            spreadsheet_id=self.keywords_sheet_id,
            target_folder=temp_path,
            sheet_name="keywords",
        )
        logger.info("Retrieved CSV.")
        sheet_dict: dict[str, list[str]] = {}
        with open(sheet_paths[0], encoding="utf-8") as csv_file:
            csv_reader: DictReader = DictReader(csv_file, delimiter=",")
            for field in csv_reader.fieldnames:
                sheet_dict[field] = []
            for row in csv_reader:
                for field in csv_reader.fieldnames:
                    if row[field] == "":
                        continue
                    sheet_dict[field].append(str(row[field]).upper())
        logger.info(f"Keywords: {sheet_dict}")
        self.keywords_sheet = sheet_dict
        keyword_count = sum(len(keywords) for keywords in sheet_dict.values())
        print_cli(f"Loaded {keyword_count} keywords.", "SETUP")

    def _retrieve_google_client(self) -> None:
        self.google_client = GoogleClient(f"{SETTINGS_FOLDER}/service_credentials.json")

    def _retrieve_settings(self, temp_path: Path):
        print_cli("Loading settings and connecting to Google services.", "SETUP")
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
        self._retrieve_keywords_csv(temp_path=temp_path)

    def orchestrate_google_scrape(self) -> None:
        print_section("GOOGLE SCRAPE")
        temp_path: Path = Path(f"{SETTINGS_FOLDER}/temp-google")
        self._retrieve_settings(temp_path)
        job_name: str = "GoogleScrape"
        search_results: dict[str, list[SearchResult]] = {}
        try:
            try:
                search_results = _run_google_job(
                    job_name=job_name,
                    keywords_sheet=self.keywords_sheet,
                    max_tries=self.max_tries,
                )
            except ACCEPTABLE_EXCEPTIONS as exc:
                logger.error(
                    f"Google scrape attempted {self.max_tries} times, ending attempts."
                )
                send_email(
                    subject=f"Repeated failure of {job_name}",
                    body=f"{traceback.format_exception(exc)} \n {exc}",
                    sender=self.email_settings["sender"],
                    recipients=self.email_settings["admin"],
                    password=self.email_settings["password"],
                )
                print_cli(
                    "Google scrape failed after all retry attempts; admins notified.",
                    "ERROR",
                )
            if search_results:
                print_section("EMAIL DELIVERY")
                print_cli("Google results found; preparing the results email.", "EMAIL")
                search_body: str = email_utils.construct_search_email(
                    results=search_results
                )
                search_subject: str = f"Relevant searches found for {datetime.now(GMT_PLUS_7).strftime('%Y-%m-%d')}"
                send_email(
                    subject=search_subject,
                    body=search_body,
                    sender=self.email_settings["sender"],
                    recipients=self.email_settings["recipients"],
                    password=self.email_settings["password"],
                )
                print_cli("Google results email sent.", "DONE")
            else:
                raise ScrapeBatchError("Google scrape has failed.")
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)
            print_cli("Google scrape temporary files removed.", "CLEANUP")

    def orchestrate_exchange_scrape(
        self, test_mode: bool = False, max_workers: int = 3
    ) -> None:
        mode = "test" if test_mode else "standard"
        print_section(f"EXCHANGE SCRAPE - {mode.upper()} MODE")
        temp_path: Path = Path(f"{PROJECT_FOLDER}/temp-exchanges")
        self._retrieve_settings(temp_path=temp_path)
        try:
            # Loop through scraping functions and run, logging successes vs failures
            failed_jobs: list[str] = []
            job_dict: dict[str, Callable] = {}
            for a in dir(scrapers):
                item = getattr(scrapers, a)
                if isinstance(item, Callable) and a.startswith("scrape_"):
                    job_dict[a.title()] = item
            print_section(
                f"RUNNING {len(job_dict)} EXCHANGE SCRAPERS ({max_workers} WORKERS)"
            )
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                job_futures: dict[Future, str] = {
                    executor.submit(
                        _run_scrape_job,
                        job_dict[job_name],
                        job_name,
                        self.keywords_sheet,
                        self.max_tries,
                    ): job_name
                    for job_name in job_dict
                }
                for future in as_completed(job_futures):
                    job_name: str = job_futures[future]
                    try:
                        future.result()
                    except ACCEPTABLE_EXCEPTIONS:
                        logger.error(
                            f"{job_name} scrape attempted {self.max_tries} times, ending attempts."
                        )
                        failed_jobs.append(job_name)

            # Done scraping, send notifs.
            print_section("EMAIL DELIVERY")
            print_cli(
                "Exchange scrapes finished; preparing the results email.", "EMAIL"
            )
            subject = f"Relevant articles found for {datetime.now(GMT_PLUS_7).strftime('%Y-%m-%d')}"
            body = email_utils.construct_webscraper_email(failed_jobs)
            send_email(
                subject=subject,
                body=body,
                sender=self.email_settings["sender"],
                recipients=self.email_settings["recipients"]
                if not test_mode
                else self.email_settings["admin"],
                password=self.email_settings["password"],
            )
            print_cli(
                "Results email sent to "
                + ("the admins." if test_mode else "recipients."),
                "DONE",
            )
            if failed_jobs:
                print_cli(
                    f"Exchange scrape completed with {len(failed_jobs)} failed job(s).",
                    "WARNING",
                )
                raise ScrapeBatchError(failed_jobs)
            print_cli("All exchange scraper jobs completed successfully.", "DONE")
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)
            print_cli("Exchange scrape temporary files removed.", "CLEANUP")
