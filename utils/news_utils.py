from datetime import datetime

class NewsInformation:
    """
    Class containing information about news articles.
    """
    news_link: str
    news_title: str
    news_date: datetime
    news_location: int
    relevant_keywords: list[str]
    retrieved_at: datetime
    def __init__(
            self,
            news_link: str,
            news_title: str,
            news_date: datetime,
            retrieved_at: datetime,
            relevant_keywords: list[str] | str,
            news_location: list[int]|int = ...
    ):
        self.news_link = news_link
        self.news_title = news_title
        self.news_date = news_date
        self.relevant_keywords = relevant_keywords
        self.retrieved_at = retrieved_at
        self.news_location = news_location if news_location is not ... else None

def notify(info: NewsInformation) -> None:
    """
    Notifies relevant parties via WhatsApp business API messages. Ideally. :)
    For now just print stuff lol.
    """
    info_string: str = (f"{info.news_link}\n"
                        f"{info.news_title}\n"
                        f"{info.news_date}\n"
                        f"{info.retrieved_at}\n"
                        f"{info.relevant_keywords}\n")
    if info.news_location is not None:
        info_string = f"{info_string}\n keywords located at page(s) {info.news_location}"
    print(info_string)