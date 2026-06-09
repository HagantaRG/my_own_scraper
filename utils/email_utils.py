import csv
from datetime import datetime

from dateutil import parser

from utils.filepaths import DATA_FOLDER

csv_headers: list[str] = ["link","title","date","keywords","retrieved_at"]
def construct_email() -> str:
    with open(f"{DATA_FOLDER}/news_data.csv", "r", newline="", encoding='utf-8') as csvfile:
        email_html: str = """
        <html>
            <head></head>
            <body>
                <p>Please find below the relevant articles found today:<br>\n
        """
        reader: csv.DictReader = csv.DictReader(csvfile, fieldnames=csv_headers)
        for row in reader:
            if row["keywords"] == "":
                continue
            retrieval_date: datetime = parser.parse(row["retrieved_at"])
            if retrieval_date.date() == datetime.today().date():
                email_html += f"<a href=\"{row["link"]}\">{row["title"]}</a> - found keyword(s) {row["keywords"]}<br>\n"
        email_html += """
                </p>
            </body>
        </html>
        """
        return email_html