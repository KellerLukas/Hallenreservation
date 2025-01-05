import logging
from src.utils.credentials import get_o365_credentials_from_env
from src.utils.fixed_o365_account import FixedAccount
from src.utils.processor import EmailProcessor
from src.utils.errors import NotAuthenticatedError
from src.utils.config import MONITORED_EMAIL_ADDRESS
from src.utils.logging import setup_logging_to_file


setup_logging_to_file()

credentials = get_o365_credentials_from_env()
account = FixedAccount(credentials)

if not account.is_authenticated:
    logging.error("Not authenticated")
    raise NotAuthenticatedError("Not authenticated")


mailbox = account.mailbox(resource=MONITORED_EMAIL_ADDRESS)
inbox = mailbox.inbox_folder()


messages = inbox.get_messages(query="isRead eq false", order_by="receivedDateTime desc")
for message in messages:
    processor = EmailProcessor(message=message, account=account)
    processor.process()
    message.mark_as_read()
