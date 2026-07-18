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