import csv
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from string import Template

from dateutil import parser

from src.scrapers.google_scrape import SearchResult
from src.utils.filepaths import DATA_FOLDER, SOURCE_FOLDER

csv_headers: list[str] = ["link", "title", "date", "keywords", "retrieved_at"]
GMT_PLUS_7 = timezone(timedelta(hours=7))
TEMPLATE_FOLDER: Path = SOURCE_FOLDER / "html_templates"


def _render_template(template_name: str, **values: str) -> str:
    template = Template((TEMPLATE_FOLDER / template_name).read_text(encoding="utf-8"))
    return template.substitute(values)


def _article_row(link: str, title: str, metadata: str = "") -> str:
    metadata_html = (
        f'<div class="article-meta">{escape(metadata)}</div>' if metadata else ""
    )
    return (
        '<div class="article">'
        f'<a class="article-link" href="{escape(link, quote=True)}">'
        f"{escape(title)}</a>{metadata_html}</div>"
    )


def construct_webscraper_email(failed_jobs: list[str]) -> str:
    site_dict: dict[str, list[list[str]]] = {}
    with (DATA_FOLDER / "news_data.csv").open(newline="", encoding="utf-8") as csvfile:
        reader: csv.DictReader = csv.DictReader(csvfile, fieldnames=csv_headers)
        for row in reader:
            if not row["keywords"]:
                continue
            retrieval_date: datetime = parser.parse(row["retrieved_at"])
            if retrieval_date.date() != datetime.now(GMT_PLUS_7).date():
                continue
            site_name = (
                row["link"].split("//", maxsplit=1)[-1].split("/", maxsplit=1)[0]
            )
            site_dict.setdefault(site_name, []).append(
                [row["link"], row["title"], row["date"], row["keywords"]]
            )

    sections = "".join(
        '<div class="section">'
        f'<h2 class="section-title">{escape(site)}</h2>'
        + "".join(
            _article_row(item[0], item[1], f"Matched: {item[3]}") for item in items
        )
        + "</div>"
        for site, items in site_dict.items()
    )
    if not sections:
        sections = (
            '<div class="empty-state">No matching articles were found today.</div>'
        )

    failure_notice = ""
    if failed_jobs:
        jobs = "".join(f"<li>{escape(job)}</li>" for job in failed_jobs)
        failure_notice = (
            '<div class="alert"><strong>Some scraper jobs failed</strong>'
            f"<ul>{jobs}</ul></div>"
        )

    article_count = sum(len(items) for items in site_dict.values())
    return _render_template(
        "webscraper_email.html",
        report_date=datetime.now(GMT_PLUS_7).strftime("%d %B %Y"),
        summary=f"{article_count} relevant article{'s' if article_count != 1 else ''} across {len(site_dict)} source{'s' if len(site_dict) != 1 else ''}",
        failure_notice=failure_notice,
        sections=sections,
    )


def construct_search_email(results: dict[str, list[SearchResult]]) -> str:
    sections = "".join(
        '<div class="section">'
        f'<h2 class="section-title">{escape(search_term)}</h2>'
        + (
            "".join(
                _article_row(
                    result.res_link,
                    result.header_text,
                    result.date.astimezone(GMT_PLUS_7).strftime("%d %b %Y"),
                )
                for result in search_results
            )
            or '<div class="empty-state">No results for this search.</div>'
        )
        + "</div>"
        for search_term, search_results in results.items()
    )
    result_count = sum(len(items) for items in results.values())
    return _render_template(
        "search_email.html",
        report_date=datetime.now(GMT_PLUS_7).strftime("%d %B %Y"),
        summary=f"{result_count} relevant result{'s' if result_count != 1 else ''} from {len(results)} search term{'s' if len(results) != 1 else ''}",
        sections=sections
        or '<div class="empty-state">No matching search results were found today.</div>',
    )
