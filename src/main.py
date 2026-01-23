import logging
from O365.mailbox import MailBox
from src.utils.credentials import get_o365_credentials_from_env
from src.utils.fixed_o365_account import FixedAccount
from src.utils.processor import EmailProcessor
from src.utils.errors import NotAuthenticatedError
from src.utils.config import MONITORED_EMAIL_ADDRESS, SUPPORT_EMAIL_ADDRESS
from src.utils.setup_logging import setup_logging_to_file


setup_logging_to_file()


def send_alert_message(mailbox: MailBox, issue: str):
    message = mailbox.new_message()
    message.subject = "HALLENRESERVATION UPLOAD ERROR"
    message.body = issue
    message.to = SUPPORT_EMAIL_ADDRESS
    message.sender = MONITORED_EMAIL_ADDRESS
    message.send()


credentials = get_o365_credentials_from_env()
account = FixedAccount(credentials)

if not account.is_authenticated:
    logging.error("Not authenticated")
    raise NotAuthenticatedError("Not authenticated")


mailbox = account.mailbox(resource=MONITORED_EMAIL_ADDRESS)
inbox = mailbox.inbox_folder()


messages = inbox.get_messages(query="isRead eq false", order_by="receivedDateTime desc")
for message in messages:
    logging.info(f"Processing message {message.subject}...")
    processor = EmailProcessor(message=message, account=account)
    try:
        processor.process()
    except Exception as e:
        logging.info("... failed, sending alert message.")
        send_alert_message(mailbox=mailbox, issue=e.__traceback__)
        continue
    logging.info("... done, marking as read.")
    message.mark_as_read()

account.connection.refresh_token()
