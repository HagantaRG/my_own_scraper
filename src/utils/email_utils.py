import csv
from datetime import datetime

from dateutil import parser

from src.utils.filepaths import DATA_FOLDER
from src.scrapers.google_scrape import SearchResult

csv_headers: list[str] = ["link","title","date","keywords","retrieved_at"]
def construct_webscraper_email() -> str:
    with open(f"{DATA_FOLDER}/news_data.csv", "r", newline="", encoding='utf-8') as csvfile:
        email_html: str = """
        <html>
            <head></head>
            <body>
                <h1>Stock Exchange Daily Webscraper</h1>\n
                <p>Please find below the relevant articles found today:<br>\n
        """
        reader: csv.DictReader = csv.DictReader(csvfile, fieldnames=csv_headers)
        site_dict: dict = dict()
        for row in reader:
            if row["keywords"] == "":
                continue
            retrieval_date: datetime = parser.parse(row["retrieved_at"])
            if retrieval_date.date() == datetime.today().date():
                site_name: str = row["link"].split("//")[1].split("/")[0]
                data: list = [row["link"], row["title"], row["date"], row["keywords"]]
                if site_name not in site_dict.keys():
                    site_dict[site_name] = [data]
                else:
                    site_dict[site_name].append(data)
            ...
        for sites in site_dict.keys():
            email_html += f"<h2>{sites}</h2>"
            for site_data in site_dict[sites]:
                email_html += f"<a href=\"{site_data[0]}\">{site_data[1]}</a> - found keyword(s) {site_data[3]}<br>\n"
        email_html += """
                </p>
            </body>
        </html>
        """
        return email_html

def construct_search_email(results: dict[str, list[SearchResult]]) -> str:
    email_html: str = """
            <html>
                <head></head>
                <body>
                    <h1>Stock Exchange Daily Webscraper</h1>\n
                    <p>Please find below the relevant articles found today:<br>\n
            """
    for search_term in results.keys():
        email_html += f"<h2>{search_term}</h2>"
        for search_results in results[search_term]:
            email_html += f"<a href=\"{search_results.res_link}\">{search_results.header_text}</a><br>\n"
    email_html += """
                    </p>
                </body>
            </html>
            """
    return email_html