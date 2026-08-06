# Python libs
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from os import makedirs
from threading import Event
from time import sleep

# Third party libs
from schedule import clear, every

# Custom libs
from src.scrapers import ScrapeOrchestrator
from src.utils.cli_utils import print_cli, print_menu, print_section
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
stdout_handler: logging.StreamHandler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.WARNING)

logging.basicConfig(
    handlers=[rotating_handler, stdout_handler],
    level=logging.INFO,
    format="[%(asctime)s] - %(filename)s:%(lineno)s - %(funcName)10s() - %(levelname)s - %(message)s ",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)
orchestrator: ScrapeOrchestrator = ScrapeOrchestrator()

stop_event: Event = Event()
try:
    print_menu()
    while True:
        user_input: str = input("\n[COMMAND] > ")
        user_input = user_input.strip()
        match user_input:
            case "help":
                print_menu()
            case "test-run":
                print_cli(
                    "Starting a one-off test scrape; results will be emailed to the admins."
                )
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
                print_cli(
                    "Daily exchange and Google scrapes are scheduled for 09:00 local time.",
                    "SCHEDULE",
                )
                stop_event: Event = run_continuously()
            case "single-scrape":
                print_cli("Starting a one-off exchange scrape.")
                run_threaded(orchestrator.orchestrate_exchange_scrape)
            case "google-scrape":
                print_cli("Starting a one-off Google scrape.")
                run_threaded(orchestrator.orchestrate_google_scrape)
            case _:
                print_cli(
                    f'Unknown command: "{user_input}". Enter "help" for options.',
                    "ERROR",
                )
        sleep(0.5)

except KeyboardInterrupt:
    print_cli("Keyboard interrupt detected; stopping.", "STOP")
except Exception as e:
    print_cli(str(e), "ERROR")
    logger.exception(e)
    raise
finally:
    stop_event.set()
    logging.shutdown()
    print_section("PROGRAM STOPPED")
    print_cli("Schedulers cleared and logging shut down.", "DONE")
