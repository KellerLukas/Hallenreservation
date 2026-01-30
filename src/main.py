import logging
import traceback
import locale
from datetime import datetime
from O365.mailbox import Message
from O365.account import Account
from src.utils.credentials import get_o365_credentials_from_env
from src.utils.fixed_o365_account import FixedAccount
from src.utils.processor import EmailProcessor
from src.utils.errors import NotAuthenticatedError
from src.utils.config import (
    DEFAULT_FROM_ADDRESS,
    MONITORED_EMAIL_ADDRESS,
    SUBSCRIPTION_META_FILE,
    SUPPORT_EMAIL_ADDRESS,
)
from src.utils.setup_logging import setup_logging_to_file
from src.utils.reservation_reminder import (
    EMAIL_NEWLINE_STR,
    ReservationReminder,
    load_subscriptions,
)

locale.setlocale(locale.LC_TIME, "de_CH.UTF-8")  

setup_logging_to_file()


def main():
    credentials = get_o365_credentials_from_env()
    account = FixedAccount(credentials)

    if not account.is_authenticated:
        logging.error("Not authenticated")
        raise NotAuthenticatedError("Not authenticated")

    process_incoming_reservations(account=account)
    process_reminders(account=account)

    account.connection.refresh_token()


def send_alert_message_for_upload(message: Message, issue: Exception) -> bool:
    fwd = message.forward()
    fwd.subject = f"HALLENRESERVATION UPLOAD ERROR: {fwd.subject}"
    fwd.body = str(issue) + EMAIL_NEWLINE_STR + traceback.format_exc() + EMAIL_NEWLINE_STR + fwd.body
    fwd.to.add(SUPPORT_EMAIL_ADDRESS)
    return fwd.send()


def send_alert_message_for_reminder(account: Account, issue: Exception) -> bool:
    mailbox = account.mailbox(resource=DEFAULT_FROM_ADDRESS)
    msg = mailbox.new_message()
    msg.to.add(SUPPORT_EMAIL_ADDRESS)
    msg.subject = "HALLENRESERVATION REMINDER ERROR"
    msg.body = str(issue) + EMAIL_NEWLINE_STR + traceback.format_exc()
    return msg.send()


def process_incoming_reservations(account: Account):
    mailbox = account.mailbox(resource=MONITORED_EMAIL_ADDRESS)
    inbox = mailbox.inbox_folder()

    messages = inbox.get_messages(
        query="isRead eq false", order_by="receivedDateTime desc"
    )
    for message in messages:
        logging.info(f"Processing message {message.subject}...")
        processor = EmailProcessor(message=message, account=account)
        try:
            processor.process()
            logging.info("... done, marking as read.")
            message.mark_as_read()
        except Exception as e:
            logging.info("... failed, sending alert message...")
            success = send_alert_message_for_upload(message=message, issue=e)
            if success:
                logging.info("... sending message successful. marking as read.")
                message.mark_as_read()
            else:
                logging.info("... failed to send message. Keep as unread.")
                message.mark_as_unread()


def process_reminders(account: Account):
    logging.info("Processing reminders...")
    try:
        subscription_metas = load_subscriptions(SUBSCRIPTION_META_FILE)
        current_weekday = datetime.now().weekday()
        targets_per_lead_day_number = {}
        for meta in subscription_metas:
            if ((current_weekday + meta.lead_days) % 7) not in meta.weekdays:
                continue
            if meta.lead_days not in targets_per_lead_day_number:
                targets_per_lead_day_number[meta.lead_days] = []
            targets_per_lead_day_number[meta.lead_days].append(meta.email)

        if len(targets_per_lead_day_number) == 0:
            logging.info("... no targets found for current weekday.")
            return
        logging.info(
            f"... identified targets per lead day number: {targets_per_lead_day_number}"
        )

        reservation_reminder = ReservationReminder(account=account)
        for lead_days, targets in targets_per_lead_day_number.items():
            reservation_reminder.remind_about_reservations_in_n_days(
                n=lead_days, recipients=targets
            )

        logging.info("... done processing reminders.")
    except Exception as e:
        logging.info("... failed, sending alert message...")
        success = send_alert_message_for_reminder(account=account, issue=e)
        if success:
            logging.info("... sending message successful.")
        else:
            logging.info("... failed to send message.")


if __name__ == "__main__":
    main()
