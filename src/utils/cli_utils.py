"""Small, thread-safe formatting helpers for CLI output."""

from threading import Lock

CLI_WIDTH = 72
_output_lock = Lock()


def print_cli(message: str, label: str = "INFO") -> None:
    """Print one consistently formatted status message."""
    with _output_lock:
        print(f"[{label}] {message}")


def print_section(title: str) -> None:
    """Visually separate major phases of a scrape."""
    rule = "=" * CLI_WIDTH
    with _output_lock:
        print(f"\n{rule}\n  {title}\n{rule}")


def print_menu() -> None:
    """Display the command menu as a distinct block."""
    rule = "=" * CLI_WIDTH
    divider = "-" * CLI_WIDTH
    with _output_lock:
        print(
            f"\n{rule}\n"
            "  SCRAPER COMMAND MENU\n"
            f"{divider}\n"
            "  help               Show this command menu\n"
            "  test-run           Run all exchange scrapers; email admins only\n"
            "  standard-schedule  Schedule exchange and Google scrapes for 09:00\n"
            "  single-scrape      Run all exchange scrapers once\n"
            "  google-scrape      Run the Google scraper once\n"
            "  Ctrl+C             Stop the program and clear schedules\n"
            f"{rule}"
        )
