import logging
import locale
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from pathlib import Path
from O365.message import Message
from O365.account import Account
from src.utils.credentials import get_o365_credentials_from_env
from src.utils.email_sender import EmailSender, EmailSendingError
from src.utils.fixed_o365_account import FixedAccount
from src.utils.typed_o365 import _mark_as_read, _mark_as_unread
from src.utils.reservation_email_processor import ReservationEmailProcessor
from src.utils.errors import NotAuthenticatedError
from src.utils.config import (
    DEFAULT_FROM_ADDRESS,
    MONITORED_EMAIL_ADDRESS,
    REMINDER_UPDATE_PREFIX,
    SUBSCRIPTION_META_FILE,
    VERTEILER_PREFIX,
    WORDPRESS_EMAIL,
)
from src.utils.setup_logging import setup_logging_to_file
from src.utils.reservation_reminder import (
    ReservationReminder,
)
from src.utils.subscription_meta import (
    SubscriptionManager,
)
from src.utils.subscription_update_email_processor import (
    SubscriptionUpdateEmailProcessor,
)

TIMESTAMP_FILE = "last_reminder_run.txt"

locale.setlocale(locale.LC_TIME, "de_CH.UTF-8")
ZONEINFO = ZoneInfo("Europe/Zurich")

# Note: may need to install this and reboot
# sudo sed -i 's/^# *\(de_CH.UTF-8 UTF-8\)/\1/' /etc/locale.gen
# sudo locale-gen
# sudo update-locale


setup_logging_to_file()


def main() -> None:
    credentials = get_o365_credentials_from_env()
    account = FixedAccount(credentials)

    if not account.is_authenticated:
        logging.error("Not authenticated")
        raise NotAuthenticatedError("Not authenticated")

    process_incoming_emails(account=account)
    process_reminders(account=account)

    account.connection.refresh_token()


def process_incoming_emails(account: Account) -> None:
    mailbox = account.mailbox(resource=MONITORED_EMAIL_ADDRESS)
    inbox = mailbox.inbox_folder()

    messages = inbox.get_messages(
        query="isRead eq false", order_by="receivedDateTime desc"
    )
    for message in messages:
        logging.info(
            f"Processing message {message.subject} from {message.sender.address} ..."
        )
        if is_reservation_email(message):
            logging.info("... is reservation email")
            process_incoming_reservation_email(account=account, message=message)
        elif is_subscription_update_email(message):
            logging.info("... is subscription update email")
            process_subscription_update_email(account=account, message=message)
        else:
            logging.info("... unknown email, skipping.")
            _mark_as_read(message)


def is_reservation_email(message: Message) -> bool:
    expected_subject_prefix = VERTEILER_PREFIX
    expected_sender_address = DEFAULT_FROM_ADDRESS
    if not message.subject.startswith(expected_subject_prefix):
        return False

    if expected_sender_address.lower() not in message.sender.address.lower():
        return False
    return True


def is_subscription_update_email(message: Message) -> bool:
    expected_subject_prefix = REMINDER_UPDATE_PREFIX
    expected_sender_address = WORDPRESS_EMAIL
    if not message.subject.startswith(expected_subject_prefix):
        return False
    if expected_sender_address.lower() not in message.sender.address.lower():
        return False
    return True


def process_incoming_reservation_email(account: Account, message: Message) -> None:
    processor = ReservationEmailProcessor(message=message, account=account)
    try:
        processor.process()
        logging.info("... done, marking as read.")
        _mark_as_read(message)
    except Exception as e:
        logging.info("... failed, sending alert message...")
        email_sender = EmailSender(account=account)
        try:
            email_sender.send_alert_message_for_upload(message=message, issue=e)
            logging.info("... marking as read.")
            _mark_as_read(message)
        except EmailSendingError as ese:
            logging.info("... failed to send alert message for upload error.")
            logging.info(ese)
            _mark_as_unread(message)


def process_subscription_update_email(account: Account, message: Message) -> None:
    processor = SubscriptionUpdateEmailProcessor(message=message, account=account)
    try:
        processor.process()
        logging.info("... done, marking as read.")
        _mark_as_read(message)
    except Exception as e:
        logging.info("... failed, sending alert message...")
        email_sender = EmailSender(account=account)
        try:
            email_sender.send_alert_message_for_subscription_update(
                message=message, issue=e
            )
            logging.info("... marking as read.")

            _mark_as_read(message)
        except EmailSendingError as ese:
            logging.info("... failed to send message. Keep as unread.")
            logging.info(ese)
            _mark_as_unread(message)


def process_reminders(account: Account) -> None:
    last_reminders_timestamp = load_last_processed_reminders_timestamp()
    now = datetime.now(ZONEINFO)
    yesterday = (now - timedelta(days=1)).date()
    today_nine_am = datetime.combine(now.date(), time(9, 0), tzinfo=ZONEINFO)

    if not (last_reminders_timestamp.date() <= yesterday and now >= today_nine_am):
        return

    logging.info("Processing reminders...")
    try:
        manager = SubscriptionManager(path=SUBSCRIPTION_META_FILE)
        targets_per_lead_day_number = (
            manager.emails_per_lead_day_number_with_reminder_due_today
        )

        if len(targets_per_lead_day_number) == 0:
            logging.info("... no targets with reminders due today, skipping.")
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
        dump_last_processed_reminders_timestamp(now)
    except Exception as e:
        logging.info("... failed, sending alert message...")
        email_sender = EmailSender(account=account)
        try:
            email_sender.send_alert_message_for_reminder(issue=e)
            logging.info("... sending message successful.")
        except EmailSendingError as ese:
            logging.info("... failed to send message.")
            logging.info(ese)


def dump_last_processed_reminders_timestamp(ts: datetime) -> None:
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
