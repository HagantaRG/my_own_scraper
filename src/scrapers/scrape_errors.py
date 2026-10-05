class UnexpectedPageFormatError(Exception):
    """Page was loaded, and all element exists, but some retrieved values did not match the expected format."""


class ScrapeBatchError(Exception):
    """Some jobs in a batch of scrapes failed."""
