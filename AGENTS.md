# AGENTS.md

## Project overview

My Own Scraper is an interactive Python CLI that monitors Asian stock-exchange announcements and Google News. It downloads a centrally maintained Google Sheets keyword list at the start of each workflow, stores matching exchange announcements in CSV, and sends HTML email reports through Gmail.

The project root is the directory containing this file. Run commands from here so the top-level `src` package and project-relative data paths resolve correctly.

## Documentation currency (mandatory)

`AGENTS.md` and `README.md` must always describe the latest implemented behavior, configuration, commands, schedules, interfaces, outputs, and development workflow.

- Before marking any change complete, review **both** files against the final implementation and update every statement affected by the change, even if the change seems small or internal.
- Keep both files consistent with each other and with the code. Update command menus, examples, source maps, operational notes, and validation instructions whenever their underlying behavior changes.
- Do not defer documentation updates, leave known-stale statements in place, or treat documentation as optional follow-up work.
- For documentation-only changes, check both files for related drift and synchronize them where applicable.
- Before finishing, verify the final diff specifically for documentation completeness as well as code correctness.

## Setup and commands

- Python: `>=3.12,<4.0` (the Ruff target is Python 3.12).
- Dependency manager: Poetry. `pyproject.toml` and `poetry.lock` are authoritative; `requirements.txt` is secondary.
- Install: `poetry install`.
- Start: `poetry run python -m src.main`.
- Lint: `poetry run ruff check src`.
- Check formatting: `poetry run ruff format --check src`.
- Format: `poetry run ruff format src`.

There is currently no automated test suite or test dependency. Do not add test scaffolding unless requested. For focused changes, use small isolated checks where possible; live workflows have external side effects described below.

### Local configuration

Copy the safe templates and fill in real values locally:

```powershell
Copy-Item settings/settings.example.toml settings/settings.toml
Copy-Item settings/service_credentials.example.json settings/service_credentials.json
```

`settings/settings.toml` contains:

- `[email-settings]`: Gmail `sender`, normal `recipients`, `admin` recipients, Gmail app `password`, and `simplified-chinese-sites` whose titles should be translated.
- `[keyword-document]`: the Google spreadsheet `sheet-id`.

The service account needs access to the keyword spreadsheet. Google News scraping also requires a locally available Chrome/Chromium-compatible browser for SeleniumBase.

Never read, print, commit, or copy real `settings/settings.toml` or `settings/service_credentials.json` into output. They are intentionally ignored by Git. Do not expose their values through logs or diagnostics.

## CLI and scheduling

`src/main.py` configures logging, constructs one `ScrapeOrchestrator`, and enters an interactive command loop. Commands run jobs in daemon background threads so the prompt remains responsive.

- `test-run`: all exchange scrapers once; results go to admins only.
- `test-single-scrape`: prompts for an exact exchange scraper function name; results go to admins only.
- `single-scrape`: all exchange scrapers once; results go to normal recipients.
- `google-scrape`: Google News workflow once.
- `standard-schedule`: runs exchange followed by Google workflows every day at 07:30 and 19:30 in the machine's local time.
- `help`: prints the command menu.
- `Ctrl+C`: stops the CLI, scheduler, and logging.

Avoid overlapping workflows: they share the CSV, temporary directories, settings, and external services. Background jobs are daemon threads, so exiting the process does not wait for them to finish.

The schedule descriptions in `README.md` and `print_menu()` currently say 09:00 and are stale; the implementation in `src/main.py` is authoritative. Keep all three in sync when changing schedules or commands.

## Application flow

### Shared startup

`ScrapeOrchestrator._retrieve_settings()` in `src/scrapers/__init__.py`:

1. Creates a `GoogleClient` using the service-account file.
2. Loads local email and spreadsheet settings through `src/utils/toml_reader.py`.
3. Downloads spreadsheet tabs as CSV through `src/google_client/__init__.py`.
4. Reads only the first returned CSV as the keyword sheet.
5. Uppercases all cell values and removes blank and duplicate values within each column.

Expected keyword columns include:

- `keywords`: general exchange matching terms.
- `stock_code_hk`: HKEX stock codes.
- `stock_code_cn`: SSE/SZSE stock codes.
- `google_search_terms`: general Google News queries.
- `inpex_search_terms`: additional Google News queries whose results are reported separately with an `[INPEX] ` subject prefix.

Changing downloaded-sheet parsing affects every workflow. Be cautious about logging the keyword sheet because its contents may be operationally sensitive.

### Exchange workflow

`ScrapeOrchestrator.orchestrate_exchange_scrape()`:

1. Discovers callable functions in `src/scrapers/exchange_scrapers.py` whose names start with `scrape_` and whose module is that file. Adding such a function automatically adds it to normal runs and `test-single-scrape`.
2. Runs selected jobs through a thread pool. It currently uses `max_workers = 1`, so exchange jobs are sequential despite older documentation describing concurrent execution.
3. Retries each job up to `DEFAULT_MAX_TRIES` (currently 5) for accepted network/browser/format failures. Unexpected `KeyError`, `ValueError`, and `IndexError` values are treated as page-format failures after retries.
4. Isolates supported job failures so other exchange jobs can finish and records failed job names for reporting.
5. Builds an HTML email from matching CSV rows retrieved on the current GMT+7 date and sends it to admins in test mode or normal recipients otherwise.
6. Sends a separate admin email if any jobs failed, then removes `temp-exchanges/`.

Exchange implementations in `src/scrapers/exchange_scrapers.py` use `curl_cffi` browser impersonation and JSON APIs for Bursa Malaysia, SGX, SSE, HKEX, and SZSE. Preserve each API's required headers, pagination conventions, URL construction, timestamp parsing, and exchange timezone. HKEX announcements are single-stock, so indexing the sole `stock` entry is intentional.

`src/scrapers/helpers.py` provides the common exchange pipeline:

- Match keywords by uppercase substring against the supplied search text; this is not token- or word-boundary matching.
- Stop a scraper when `parse_announcement()` returns `None` for an announcement older than its cutoff. Scrapers assume announcements are encountered in an order where this stop is valid.
- Append relevant rows to `data/news_data.csv` with columns `link,title,date,keywords,retrieved_at`; the file has no separate header row.
- Treat `(link, title)` as the duplicate key.
- Protect CSV checks/writes with a `FileLock`.
- Track total and relevant counts in `RunTally`.

### Google News workflow

`ScrapeOrchestrator.orchestrate_google_scrape()` runs `google_search_scrape()` from `src/scrapers/google_scrape.py`:

1. Starts a headless, incognito SeleniumBase browser with anti-detection enabled.
2. Searches Google News for each `google_search_terms` entry followed by each `inpex_search_terms` entry, restricted to the past day and sorted by date. Progress covers the combined term count.
3. Follows result pagination and collects heading, link, timestamp, and originating search term.
4. Keeps general and INPEX results in separate dictionaries so identical terms in different columns remain independent.
5. Uses exponential randomized backoff for CAPTCHAs; terms that remain blocked are skipped and reported to admins.
6. Retries the overall Google job through the shared retry wrapper.
7. Sends general and INPEX HTML reports separately to the normal recipients. The INPEX subject prepends `[INPEX] ` to the general report subject. An absent or empty INPEX column produces no INPEX report.
8. Treats the run as finding nothing only when both groups have no results, then removes `settings/temp-google/` afterward.

Google selectors and CAPTCHA behavior are external and brittle. Verify format changes against the actual page rather than assuming old selectors still apply. Avoid broad live probing without approval because it generates network traffic and may trigger CAPTCHAs.

### Email generation and delivery

- `src/utils/email_utils.py` renders `src/html_templates/webscraper_email.html` and `search_email.html` using `string.Template`.
- Exchange emails group rows by link hostname and include only rows whose `retrieved_at` date is today in GMT+7, not all rows with today's announcement date.
- Hostnames listed in `simplified-chinese-sites` have titles translated from Chinese to English, introducing another external service dependency.
- Dynamic titles, links, and metadata are HTML-escaped. Preserve escaping and all required `${...}` template substitutions when editing markup.
- `samples/google_search_email_preview.html` is an example populated Google report; use populated local previews for HTML changes rather than sending real email solely for visual verification.
- `src/smtp_functions/__init__.py` sends HTML through Gmail SMTP SSL on port 465 and retries SMTP/OS errors.

## Source map

- `src/main.py`: CLI, logging, schedules, process lifecycle.
- `src/scrapers/__init__.py`: orchestration, discovery, settings refresh, retries, failure isolation, workflow cleanup, email triggers.
- `src/scrapers/exchange_scrapers.py`: exchange-specific JSON API clients and parsers.
- `src/scrapers/helpers.py`: matching, age cutoffs, CSV persistence, deduplication, locking, run tallies.
- `src/scrapers/google_scrape.py`: Selenium Google News collection and CAPTCHA handling.
- `src/scrapers/scrape_errors.py`: scrape-specific exception types.
- `src/google_client/__init__.py`: service-account Sheets metadata and CSV export.
- `src/smtp_functions/__init__.py`: Gmail delivery.
- `src/utils/email_utils.py`: report selection, translation, escaping, and HTML rendering.
- `src/utils/cli_utils.py`: synchronized CLI messages, errors, spinner, progress bar, menu.
- `src/utils/thread_utils.py`: daemon job and scheduler threads.
- `src/utils/filepaths.py`: project-root-derived paths; prefer these constants over hard-coded paths.
- `src/utils/constants.py`: timezones and retry default.
- `src/utils/news_utils.py`: exchange announcement data container.
- `src/utils/toml_reader.py`: cached TOML section loader.

## Generated and persistent files

- `data/news_data.csv`: persistent relevant exchange results; ignored by Git.
- `data/news_data.csv.lock`: CSV interprocess lock.
- `logs/scraper.log`: INFO-level application log, rotated at midnight with 10 backups; console logging starts at WARNING.
- `temp-exchanges/`: per-run spreadsheet downloads, removed after exchange workflows.
- `settings/temp-google/`: per-run spreadsheet downloads, removed after Google workflows.
- `downloaded_files/` and `__pycache__/`: local generated artifacts, not application source.

Do not delete, reset, or rewrite existing CSV data or logs as a shortcut during development or verification. Inspect Git status before finishing and leave unrelated user/generated files alone.

## Change and verification guidance

- Match the existing typed, function-oriented style and use the configured Ruff rules. Keep public function names and sheet-column contracts stable unless intentionally changing the interface.
- Put exchange-specific parsing in `exchange_scrapers.py`; put behavior shared by exchanges in `helpers.py`; keep orchestration and notification policy in `ScrapeOrchestrator`.
- Apply the mandatory documentation-currency rule above to every change; explicitly check both `AGENTS.md` and `README.md`, including command menus, schedules, paths, configuration, CSV fields, and report placeholders.
- Run Ruff checks after source changes. Validate pure parsing, rendering, and matching functions with local fixtures or in-memory data where possible.
- Treat every full CLI scrape as a live operation: it downloads configuration, calls external sites, may write `data/news_data.csv`, may translate titles, and sends real email. Even test exchange commands send email to admins. Obtain explicit approval before using them for verification, and prefer a single named scraper or mocked boundaries when they are sufficient.
- Check final diffs for credentials, live recipient addresses, downloaded sheets, generated CSV/log files, and temporary browser artifacts.
