# Python libs
import logging
from logging.handlers import TimedRotatingFileHandler
from os import makedirs
from threading import Event
from time import sleep

# Third party libs
from schedule import clear, every

# Custom libs
from src.scrapers import ScrapeOrchestrator
from src.utils.filepaths import LOGS_FOLDER
from src.utils.thread_utils import run_continuously, run_threaded

logger = logging.getLogger(__name__)

"""
This should be the main thing that orchestrates all the scrapers and various other tasks. 
"""

log_file: str = f"{LOGS_FOLDER}/scraper.log"
makedirs(f"{LOGS_FOLDER}", exist_ok=True)
rotating_handler: TimedRotatingFileHandler = TimedRotatingFileHandler(
    filename=log_file, encoding="utf-8", when="midnight", backupCount=10
)
logging.basicConfig(
    handlers=[rotating_handler],
    level=logging.INFO,
    format="[%(asctime)s] - %(filename)s:%(lineno)s - %(funcName)10s() - %(levelname)s - %(message)s ",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)
orchestrator: ScrapeOrchestrator = ScrapeOrchestrator()

stop_event: Event = Event()
try:
    while True:
        user_input: str = input(
            'Awaiting user input for scraper. Please enter "help" to get a list of valid commands.\n'
        )
        user_input = user_input.strip()
        match user_input:
            case "help":
                print(
                    "Available commands:\n"
                    "test-run: Carries out a one-off run of the *whole* scraper, emailing only the admins.\n"
                    "standard-schedule: Standard scheduled scraper, running at 9:00 AM local time every day.\n"
                    "single-scrape: Runs the scraper once. Does not schedule anything.\n"
                    "single-site: Scrapes one of the supported websites. Available codes will be displayed on selection."
                    "google-scrape: Only runs the google scraper."
                )
            case "test-run":
                run_threaded(orchestrator.orchestrate_exchange_scrape, test_mode=True)
            case "standard-schedule":
                # The way this works is that there is one long-running thread that exists for the scheduler
                # and *that* thread will spin up another daemon thread for the daily scrape jobs.
                clear()
                stop_event.set()
                logger.info(
                    "Cleared any existing jobs, cleared previously existing schedulers."
                )
                stock_scrape_schedule = (
                    every()
                    .day.at("09:00")
                    .do(run_threaded, orchestrator.orchestrate_exchange_scrape)
                )
                google_scrape_schedule = (
                    every()
                    .day.at("09:00")
                    .do(run_threaded, orchestrator.orchestrate_google_scrape)
                )
                logger.info("9AM scrapes scheduled.")
                stop_event: Event = run_continuously()
            case "single-scrape":
                run_threaded(orchestrator.orchestrate_exchange_scrape)
            case "single-site":
                site_code: str = input(
                    "bursa_my: The Malaysian stock exchange website.\n"
                    "szse: The Shenzhen stock exchange website.\n"
                    "sse: The Shanghai stock exchange website.\n"
                    "sgx: The Singaporean stock exchange website.\n"
                    "hkx: The Hong Kong stock exchange website.\n"
                )
                site_code = site_code.strip()
                site_list: list[str] = ["bursa_my", "szse", "sgx", "hkx", "sse"]
                if site_code not in site_list:
                    print("Invalid site code.")
                else:
                    run_threaded(
                        orchestrator.orchestrate_exchange_scrape,
                        test_mode=True,
                        target_site=site_code,
                    )
            case "google-scrape":
                run_threaded(orchestrator.orchestrate_google_scrape)
            case _:
                print("Invalid command.")
        sleep(0.5)

except KeyboardInterrupt:
    print("Keyboard interrupt detected, breaking.")
except Exception as e:
    print(e)
    logging.exception(e)
    raise
finally:
    stop_event.set()
    logging.shutdown()
    print("Program execution stopped. Cleared schedulers.")
