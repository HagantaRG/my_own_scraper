"""Small, thread-safe formatting helpers for CLI output."""

import logging
import sys
import traceback
from collections.abc import Callable
from os import environ
from threading import Event, Lock, Thread
from time import monotonic

CLI_WIDTH = 72
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_BLUE = "\033[34m"
ANSI_MAGENTA = "\033[35m"
ANSI_CYAN = "\033[36m"
ANSI_RESET = "\033[0m"
LABEL_COLORS = {
    "CLEANUP": ANSI_CYAN,
    "DONE": ANSI_GREEN,
    "EMAIL": ANSI_MAGENTA,
    "ERROR": ANSI_RED,
    "INFO": ANSI_CYAN,
    "RETRY": ANSI_RED,
    "RUN": ANSI_BLUE,
    "SCHEDULE": ANSI_MAGENTA,
    "SETUP": ANSI_CYAN,
    "STOP": ANSI_YELLOW,
    "STOPPED": ANSI_YELLOW,
    "WARNING": ANSI_RED,
}
_output_lock = Lock()


def _supports_color() -> bool:
    """Return whether ANSI colors are appropriate for the current output."""
    return "NO_COLOR" not in environ and sys.stdout.isatty()


def _colorize(message: str, color: str | None) -> str:
    if color is None or not _supports_color():
        return message
    return f"{color}{message}{ANSI_RESET}"


def _format_cli_message(message: str, label: str) -> str:
    line = f"[{label}] {message}"
    return _colorize(line, LABEL_COLORS.get(label.upper()))


def _clear_live_line() -> None:
    sys.stdout.write("\r" + (" " * CLI_WIDTH) + "\r")
    sys.stdout.flush()


def print_cli(message: str, label: str = "INFO") -> None:
    """Print one consistently formatted status message."""
    with _output_lock:
        _clear_live_line()
        print(_format_cli_message(message, label))


def print_error(exception: BaseException, context: str | None = None) -> None:
    """Render an exception as one uninterrupted, visually distinct CLI block."""
    trace = "".join(
        traceback.format_exception(type(exception), exception, exception.__traceback__)
    ).rstrip()
    context_line = f"Worker: {context}\n" if context else ""
    _print_error_block(f"{context_line}{trace}")


def _print_error_block(message: str) -> None:
    """Print error text as one synchronized block, clearing live CLI output first."""
    heading = "[ERROR MESSAGE]".center(CLI_WIDTH, "-")
    footer = "[END OF ERROR MESSAGE]".center(CLI_WIDTH, "-")
    color_start = ANSI_RED if _supports_color() else ""
    color_end = ANSI_RESET if _supports_color() else ""

    with _output_lock:
        _clear_live_line()
        print(f"\n{color_start}{heading}\n{message}\n{footer}{color_end}")


class CliStreamHandler(logging.StreamHandler):
    """Send console log errors through the same atomic CLI error renderer."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            if record.levelno >= logging.ERROR:
                _print_error_block(message)
            else:
                with _output_lock:
                    _clear_live_line()
                    print(_colorize(message, ANSI_RED))
        except Exception:  # noqa: BLE001
            self.handleError(record)


def print_section(title: str) -> None:
    """Visually separate major phases of a scrape."""
    rule = "=" * CLI_WIDTH
    with _output_lock:
        _clear_live_line()
        print(f"\n{rule}\n  {title}\n{rule}")


def print_menu() -> None:
    """Display the command menu as a distinct block."""
    rule = "=" * CLI_WIDTH
    divider = "-" * CLI_WIDTH
    with _output_lock:
        _clear_live_line()
        print(
            f"\n{rule}\n"
            "  SCRAPER COMMAND MENU\n"
            f"{divider}\n"
            "  help               Show this command menu\n"
            "  test-run           Run all exchange scrapers; email admins only\n"
            "  test-single-scrape Run one named exchange scraper; email admins only\n"
            "  standard-schedule  Schedule exchange and Google scrapes for 09:00\n"
            "  single-scrape      Run all exchange scrapers once\n"
            "  google-scrape      Run the Google scraper once\n"
            "  Ctrl+C             Stop the program and clear schedules\n"
            f"{rule}"
        )


class Spinner:
    """Display an animated status line until the associated work finishes."""

    frames = ("|", "/", "-", "\\")

    def __init__(self, message: str, interval: float = 0.12) -> None:
        self.message = message
        self.interval = interval
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._started_at = 0.0

    def start(self) -> None:
        self._started_at = monotonic()
        self._stop_event.clear()
        self._thread = Thread(target=self._animate, daemon=True)
        self._thread.start()

    def _animate(self) -> None:
        frame_index = 0
        while not self._stop_event.wait(self.interval):
            elapsed = monotonic() - self._started_at
            line = (
                f"[{self.frames[frame_index % len(self.frames)]}] "
                f"{self.message} ({elapsed:.0f}s)"
            )
            with _output_lock:
                sys.stdout.write(f"\r{line[:CLI_WIDTH]:<{CLI_WIDTH}}")
                sys.stdout.flush()
            frame_index += 1

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.interval * 2))
        with _output_lock:
            _clear_live_line()

    def __enter__(self) -> "Spinner":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()


class ProgressBar:
    """Render determinate CLI progress from a completed-item callback."""

    def __init__(self, label: str, width: int = 30) -> None:
        self.label = label
        self.width = width
        self._last_completed = 0
        self._total = 0
        self._last_item = ""

    def update(self, completed: int, total: int, item: str = "") -> None:
        self._last_completed = completed
        self._total = total
        self._last_item = item
        self._render()

    def _render(self, status: str = "") -> None:
        completed = self._last_completed
        total = self._total
        fraction = completed / total if total else 1.0
        filled = min(self.width, round(self.width * fraction))
        bar = "#" * filled + "-" * (self.width - filled)
        item = status or self._last_item
        suffix = f" {item}" if item else ""
        line = f"{self.label} [{bar}] {completed}/{total}{suffix}"
        with _output_lock:
            sys.stdout.write(f"\r{line[:CLI_WIDTH]:<{CLI_WIDTH}}")
            sys.stdout.flush()

    def set_status(self, message: str | None) -> None:
        """Temporarily replace the current item with an operational status."""
        self._render(status=message or "")

    def callback(self) -> Callable[[int, int, str], None]:
        return self.update

    def finish(self, succeeded: bool = True) -> None:
        with _output_lock:
            _clear_live_line()
            status = "DONE" if succeeded else "STOPPED"
            message = f"{self.label}: {self._last_completed}/{self._total} processed."
            print(_format_cli_message(message, status))

    def __enter__(self) -> "ProgressBar":
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: object,
    ) -> None:
        self.finish(succeeded=exception_type is None)
