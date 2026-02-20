import logging
import locale
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from pathlib import Path
from O365.message import Message
from src.utils.credentials import get_o365_credentials_from_env
from src.email.email_sender import EmailSender, EmailSendingError
from src.utils.fixed_o365_account import FixedAccount
from src.utils.typed_o365 import _mark_as_read, _mark_as_unread
from src.email.email_processors.reservation_email_processor import (
    ReservationEmailProcessor,
)
from src.utils.errors import NotAuthenticatedError
from src.config import (
    DEFAULT_FROM_ADDRESS,
    MONITORED_EMAIL_ADDRESS,
    INCOMING_REMINDER_UPDATE_PREFIX,
    SUBSCRIPTION_META_FILE,
    INCOMING_RESERVATION_PREFIX,
    WORDPRESS_EMAIL,
)
from src.email.reservation_reminder_handler import (
    ReservationReminderHandler,
)
from src.utils.subscription_meta import (
    SubscriptionManager,
)
from src.email.email_processors.subscription_update_email_processor import (
    SubscriptionUpdateEmailProcessor,
)


# Note: may need to install this and reboot
# sudo sed -i 's/^# *\(de_CH.UTF-8 UTF-8\)/\1/' /etc/locale.gen
# sudo locale-gen
# sudo update-locale
locale.setlocale(locale.LC_TIME, "de_CH.UTF-8")
ZONEINFO = ZoneInfo("Europe/Zurich")
TIMESTAMP_FILE = "last_reminder_run.txt"


class Orchestrator:
    def __init__(self) -> None:
        self.account = self._set_up_account()
        self.email_sender = EmailSender(account=self.account)

    def run(self) -> None:
        self.process_incoming_emails()
        self.send_reminders()

    def process_incoming_emails(self) -> None:
        mailbox = self.account.mailbox(resource=MONITORED_EMAIL_ADDRESS)
        inbox = mailbox.inbox_folder()
        messages = inbox.get_messages(
            query="isRead eq false", order_by="receivedDateTime desc"
        )
        for message in messages:
            logging.info(
                f"Processing message {message.subject} from {message.sender.address} ..."
            )
            if self._is_reservation_email(message):
                logging.info("... is reservation email")
                self.process_incoming_reservation_email(message)
            elif self._is_subscription_update_email(message):
                logging.info("... is subscription update email")
                self.process_subscription_update_email(message)
            else:
                logging.info("... unknown email, skipping.")
                _mark_as_read(message)

    def process_incoming_reservation_email(self, message: Message) -> None:
        try:
            processor = ReservationEmailProcessor(message=message, account=self.account)
            processor.process()
            logging.info("... done, marking as read.")
            _mark_as_read(message)
        except Exception as e:
            logging.info("... failed, sending alert message...")
            try:
                self.email_sender.send_alert_message_for_upload(
                    message=message, issue=e
                )
                logging.info("... marking as read.")
                _mark_as_read(message)
            except EmailSendingError as ese:
                logging.info("... failed to send alert message for upload error.")
                logging.info(ese)
                _mark_as_unread(message)

    def process_subscription_update_email(self, message: Message) -> None:
        try:
            processor = SubscriptionUpdateEmailProcessor(
                message=message, account=self.account
            )
            processor.process()
            logging.info("... done, marking as read.")
            _mark_as_read(message)
        except Exception as e:
            logging.info("... failed, sending alert message...")
            try:
                self.email_sender.send_alert_message_for_subscription_update(
                    message=message, issue=e
                )
                logging.info("... marking as read.")
                _mark_as_read(message)
            except EmailSendingError as ese:
                logging.info("... failed to send message. Keep as unread.")
                logging.info(ese)
                _mark_as_unread(message)

    def send_reminders(self) -> None:
        try:
            last_reminders_timestamp = self._load_last_processed_reminders_timestamp()
            now = datetime.now(ZONEINFO)
            yesterday = (now - timedelta(days=1)).date()
            today_nine_am = datetime.combine(now.date(), time(9, 0), tzinfo=ZONEINFO)

            if not (
                last_reminders_timestamp.date() <= yesterday and now >= today_nine_am
            ):
                return

            logging.info("Processing reminders...")

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

            reservation_reminder = ReservationReminderHandler(account=self.account)
            for lead_days, targets in targets_per_lead_day_number.items():
                reservation_reminder.remind_about_reservations_in_n_days(
                    n=lead_days, recipients=targets
                )

            logging.info("... done processing reminders.")
            self._dump_last_processed_reminders_timestamp(now)
        except Exception as e:
            logging.info("... failed, sending alert message...")
            try:
                self.email_sender.send_alert_message_for_reminder(issue=e)
                logging.info("... sending message successful.")
            except EmailSendingError as ese:
                logging.info("... failed to send message.")
                logging.info(ese)

    def prettyprint_subscriptions(self) -> None:
        manager = SubscriptionManager(path=SUBSCRIPTION_META_FILE)
        manager.pretty_print_subscriptions()

    def _is_reservation_email(self, message: Message) -> bool:
        expected_subject_prefix = INCOMING_RESERVATION_PREFIX
        expected_sender_address = DEFAULT_FROM_ADDRESS
        if not message.subject.startswith(expected_subject_prefix):
            return False

        if expected_sender_address.lower() not in message.sender.address.lower():
            return False
        return True

    def _is_subscription_update_email(self, message: Message) -> bool:
        expected_subject_prefix = INCOMING_REMINDER_UPDATE_PREFIX
        expected_sender_address = WORDPRESS_EMAIL
        if not message.subject.startswith(expected_subject_prefix):
            return False
        if expected_sender_address.lower() not in message.sender.address.lower():
            return False
        return True

    def _set_up_account(self) -> FixedAccount:
        credentials = get_o365_credentials_from_env()
        account = FixedAccount(credentials)

        if not account.is_authenticated:
            logging.error("Not authenticated")
            raise NotAuthenticatedError("Not authenticated")

        account.connection.refresh_token()
        return account

    @staticmethod
    def _dump_last_processed_reminders_timestamp(ts: datetime) -> None:
        path = Path(TIMESTAMP_FILE)

        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=ZONEINFO)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(ts.isoformat(), encoding="utf-8")

    @staticmethod
    def _load_last_processed_reminders_timestamp() -> datetime:
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
