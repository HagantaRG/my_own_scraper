import logging
import smtplib
from email.mime.text import MIMEText
from smtplib import SMTPException
from time import sleep

logger = logging.getLogger(__name__)


def send_email(
    subject: str,
    body: str,
    sender: str,
    recipients: list[str],
    password: str,
    max_tries: int = 5,
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
            return None
        except SMTPException as network_error:
            if tries > max_tries:
                logging.error(
                    f"Error encountered in email sending {max_tries} times. Emails have NOT been sent."
                )
                return None
            else:
                logging.info(
                    f"Network encountered during email sending try number {tries}, trying up to 5 times."
                )
                logging.info(network_error)
                sleep(1)
    return None
