import logging
import traceback
from O365.mailbox import Message
from src.utils.credentials import get_o365_credentials_from_env
from src.utils.fixed_o365_account import FixedAccount
from src.utils.processor import EmailProcessor
from src.utils.errors import NotAuthenticatedError
from src.utils.config import MONITORED_EMAIL_ADDRESS, SUPPORT_EMAIL_ADDRESS
from src.utils.setup_logging import setup_logging_to_file


setup_logging_to_file()


def send_alert_message(message: Message, issue: Exception):
    fwd = message.forward()
    fwd.subject = f"HALLENRESERVATION UPLOAD ERROR: {fwd.subject}"
    fwd.body = str(issue) + "\n\n" + traceback.format_exc() + "\n\n" + fwd.body
    fwd.to.add(SUPPORT_EMAIL_ADDRESS)
    success = fwd.send()
    logging.info(f"... sending message successful: {success}")


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
        send_alert_message(message=message, issue=e)
        continue
    logging.info("... done, marking as read.")
    message.mark_as_read()

account.connection.refresh_token()
