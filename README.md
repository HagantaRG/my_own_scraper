# My Own Scraper

My Own Scraper is a command-line news aggregation tool that monitors several
Asian stock exchanges and Google News for articles and announcements matching a
centrally maintained keyword list. It records relevant exchange announcements
in CSV format and sends HTML email summaries to configured recipients.

The application is intended to support repeated monitoring rather than one-off
page downloads. It retrieves the latest keywords at the beginning of every run,
retries transient scraping failures, reports progress in the terminal, and can
run automatically each day.

> [!CAUTION]
> **AI usage disclaimer**
>
> Much of the project's command-line user interface, this README.md, and its associated
> messaging was generated with assistance from AI. OpenAI Codex was also used
> to help inspect, analyse, and explain the program's backend control flow,
> including its scraping orchestration, retry handling, concurrency, and
> file-access behaviour. However, all non-UI code was written by myself. AI-assisted output should be reviewed and tested
> before it is relied upon in a production environment.

---

## What it does

The exchange workflow currently collects announcements from:

- Hong Kong Exchanges and Clearing (HKEX)
- Singapore Exchange (SGX)
- Bursa Malaysia
- Shenzhen Stock Exchange (SZSE)
- Shanghai Stock Exchange (SSE)

Exchange scrapers run concurrently through a thread pool. Each scraper uses its
own browser session, filters announcements against the configured keywords, and
appends relevant results to `data/news_data.csv`. A file lock protects CSV
writes made by concurrent scraper threads.

The separate Google workflow searches Google News using terms from the same
keyword spreadsheet. Matching search results are formatted directly into an
email report.
---

## Requirements

- Python 3.12 or newer
- [Poetry](https://python-poetry.org/) for dependency management
- A locally available Chrome/Chromium-compatible browser for SeleniumBase
- A Google Cloud service account with read access to the keyword spreadsheet
- A Gmail account and app password for sending notification emails

---

## Installation

Clone the repository, enter its directory, and install the locked dependencies:

```powershell
poetry install
```

`pyproject.toml` and `poetry.lock` are the authoritative dependency files.

---

## Configuration

Create `settings/settings.toml` with the following structure:

```toml
[email-settings]
sender = "sender@example.com"
recipients = ["recipient@example.com"]
admin = ["admin@example.com"]
password = "gmail-app-password"

[keyword-document]
sheet-id = "google-spreadsheet-id"
```

Place the Google service-account credentials at:

```text
settings/service_credentials.json
```

The spreadsheet is expected to contain a worksheet that can be exported as CSV.
Its headings are used as keyword groups by the scrapers. Exchange searches use a
`keywords` column, while Google News searches use a `google_search_terms` column.

> **Security:** `settings.toml` and `service_credentials.json` contain secrets.
> Do not commit them, paste them into issue reports, or include them in logs.
> Use a Gmail app password rather than the account's primary password.

---

## Running the application

Start the CLI from the repository root:

```powershell
poetry run python -m src.main
```

The application displays a command menu with these options:

| Command | Purpose |
| --- | --- |
| `help` | Display the command menu again. |
| `test-run` | Run all exchange scrapers once and email only the administrators. |
| `standard-schedule` | Schedule exchange and Google scrapes for 09:00 local time each day. |
| `single-scrape` | Run all exchange scrapers once and email the normal recipients. |
| `google-scrape` | Run only the Google News scraper. |

Use `Ctrl+C` to stop the application and clear its in-process schedules.

Scrape commands run in background threads, so the CLI can continue accepting
commands while work is in progress. Avoid deliberately starting overlapping
copies of the same complete workflow because they share configuration and
temporary paths.

---

## Output and logging

- `data/news_data.csv` stores relevant exchange announcements.
- `logs/scraper.log` contains application and diagnostic logging.
- `temp-exchanges/` holds temporary exchange-run files.
- `settings/temp-google/` holds temporary Google-run files.

Temporary run directories are removed at the end of their corresponding
workflow. Log files rotate at midnight, with up to ten backups retained.

---

## Development checks

Run linting and verify formatting with Ruff:

```powershell
poetry run ruff check src
poetry run ruff format --check src
```

Apply the configured formatter with:

```powershell
poetry run ruff format src
```
