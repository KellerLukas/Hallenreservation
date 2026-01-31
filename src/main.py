import logging
import traceback
import locale
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from pathlib import Path
from O365.mailbox import Message
from O365.account import Account
from src.utils.credentials import get_o365_credentials_from_env
from src.utils.fixed_o365_account import FixedAccount
from src.utils.reservation_email_processor import ReservationEmailProcessor
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

TIMESTAMP_FILE = "last_reminder_run.txt"

locale.setlocale(locale.LC_TIME, "de_CH.UTF-8")
ZONEINFO = ZoneInfo("Europe/Zurich")

# Note: may need to install this and reboot
# sudo sed -i 's/^# *\(de_CH.UTF-8 UTF-8\)/\1/' /etc/locale.gen
# sudo locale-gen
# sudo update-locale


setup_logging_to_file()


def main():
    credentials = get_o365_credentials_from_env()
    account = FixedAccount(credentials)

    if not account.is_authenticated:
        logging.error("Not authenticated")
        raise NotAuthenticatedError("Not authenticated")

    process_incoming_emails(account=account)

    last_reminders_timestamp = load_last_processed_reminders_timestamp()
    now = datetime.now(ZONEINFO)
    yesterday = (now - timedelta(days=1)).date()
    today_nine_am = datetime.combine(now.date(), time(9, 0), tzinfo=ZONEINFO)

    if last_reminders_timestamp.date() <= yesterday and now >= today_nine_am:
        process_reminders(account=account)
        dump_last_processed_reminders_timestamp(now)

    account.connection.refresh_token()


def send_alert_message_for_upload(message: Message, issue: Exception) -> bool:
    fwd = message.forward()
    fwd.subject = f"HALLENRESERVATION UPLOAD ERROR: {fwd.subject}"
    fwd.body = (
        str(issue)
        + EMAIL_NEWLINE_STR
        + traceback.format_exc()
        + EMAIL_NEWLINE_STR
        + fwd.body
    )
    fwd.to.add(SUPPORT_EMAIL_ADDRESS)
    return fwd.send()


def send_alert_message_for_reminder(account: Account, issue: Exception) -> bool:
    mailbox = account.mailbox(resource=DEFAULT_FROM_ADDRESS)
    msg = mailbox.new_message()
    msg.to.add(SUPPORT_EMAIL_ADDRESS)
    msg.subject = "HALLENRESERVATION REMINDER ERROR"
    msg.body = str(issue) + EMAIL_NEWLINE_STR + traceback.format_exc()
    return msg.send()


def process_incoming_emails(account: Account):
    mailbox = account.mailbox(resource=MONITORED_EMAIL_ADDRESS)
    inbox = mailbox.inbox_folder()

    messages = inbox.get_messages(
        query="isRead eq false", order_by="receivedDateTime desc"
    )
    for message in messages:
        logging.info(f"Processing message {message.subject}...")
        if is_reservation_email(message):
            logging.info("... is reservation email")
            return process_incoming_reservation_email(account=account, message=message)
        if is_subscription_update_email(message):
            logging

def is_reservation_email(message: Message) -> bool:
    pass
                
def process_incoming_reservation_email(account: Account, message: Message):
    processor = ReservationEmailProcessor(message=message, account=account)
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


def dump_last_processed_reminders_timestamp(ts: datetime):
    path = Path(TIMESTAMP_FILE)

    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZONEINFO)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ts.isoformat(), encoding="utf-8")


def load_last_processed_reminders_timestamp() -> datetime:
    path = Path(TIMESTAMP_FILE)

    if not path.exists():
        # First run: pretend last run was long ago
        return datetime.min.replace(tzinfo=ZONEINFO)

    raw = path.read_text(encoding="utf-8").strip()
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        raise ValueError(
            f"Invalid timestamp format in {path}: {raw!r} (expected ISO-8601)"
        )


if __name__ == "__main__":
    main()
