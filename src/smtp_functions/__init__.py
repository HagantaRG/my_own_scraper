import logging
import smtplib
from email.mime.text import MIMEText
from smtplib import SMTPException
from time import sleep

from src.utils.constants import DEFAULT_MAX_TRIES

logger = logging.getLogger(__name__)


def send_email(  # noqa: PLR0913, PLR0917
    subject: str,
    body: str,
    sender: str,
    recipients: list[str],
    password: str,
    max_tries: int = DEFAULT_MAX_TRIES,
) -> None:
    tries: int = 0
    while tries <= max_tries:
        try:
            tries += 1
            msg = MIMEText(body, "html")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = ", ".join(recipients)
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp_server:
                smtp_server.login(sender, password)
                smtp_server.sendmail(sender, recipients, msg.as_string())
            logger.info(f"Email sent to {recipients} from {sender}")
            return
        except SMTPException as network_error:
            if tries > max_tries:
                logger.error(
                    f"Error encountered in email sending {max_tries} times. Emails have NOT been sent."
                )
                return
            logger.info(
                f"Network encountered during email sending try number {tries}, trying up to 5 times."
            )
            logger.info(network_error)
            sleep(1)
    return
