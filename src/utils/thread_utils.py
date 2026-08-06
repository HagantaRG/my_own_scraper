import logging
from collections.abc import Callable
from threading import Event, Thread
from time import sleep

from schedule import run_pending

logger = logging.getLogger(__name__)


def run_threaded(job_func: Callable, *args, **kwargs):
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
    logger.info("Background scheduler started.")
    return stopper_event
