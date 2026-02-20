import logging
from typing import List, Optional
from O365.account import Account
from O365.message import Message
from src.config import (
    SUBSCRIPTION_META_FILE,
)
from src.email.email_processors.email_processor_base import EmailProcessorBase
from src.email.email_sender import EmailSender
from src.utils.subscription_meta import (
    SubscriptionManager,
    SubscriptionMeta,
    SUBSCRIPTION_META_VALUE_TYPES,
)

OPTIONAL_SUBSCRIPTION_UPDATE_KEYS = ["weekdays", "reminder_lead_days"]


class SubscriptionUpdateEmailProcessor(EmailProcessorBase):
    def __init__(self, message: Message, account: Account):
        super().__init__(message, account)
        self.manager = SubscriptionManager(path=SUBSCRIPTION_META_FILE)
        self.email_sender = EmailSender(account=account)

    def process(self) -> None:
        logging.info(
            f"... starting process for subscription update message {self.message.subject}"
        )
        content = self.message.body
        subscription_meta = self.get_subscription_meta_from_content(content)
        logging.info(f"... parsed subscription meta: {subscription_meta}")
        self.manager.add_or_update_subscription(subscription_meta)
        logging.info(f"... updated subscription for {subscription_meta.email}")
        self.email_sender.send_subscription_update_confirmation_email(subscription_meta)
        logging.info(
            f"... sent subscription update confirmation email to {subscription_meta.email}"
        )
        logging.info(f"... done processing message {self.message.subject}")

    def get_subscription_meta_from_content(self, content: str) -> SubscriptionMeta:
        lines = content.splitlines()
        reminder_lead_days = self._extract_value_for_key_from_lines(
            "reminder_lead_days", lines
        )
        receive_reminders = self._extract_value_for_key_from_lines(
            "reminder_emails", lines
        )
        if not receive_reminders:
            reminder_lead_days = None
        return SubscriptionMeta(
            email=assert_is_string(
                self._extract_value_for_key_from_lines("email", lines)
            ),
            weekdays=assert_is_list_of_integers(
                self._extract_value_for_key_from_lines("weekdays", lines)
            ),
            reminder_lead_days=assert_is_integer_or_none(reminder_lead_days),
            immediate_notifications=assert_is_boolean(
                self._extract_value_for_key_from_lines("immediate_notifications", lines)
            ),
        )

    def _extract_value_for_key_from_lines(
        self, key: str, lines: List[str]
    ) -> SUBSCRIPTION_META_VALUE_TYPES:
        line = self._find_line_starting_with_key(key, lines)
        if key == "reminder_lead_days":
            return int(line)
        if key == "weekdays":
            weekdays = line.split(",")
            weekday_map = {
                "Montag": 0,
                "Dienstag": 1,
                "Mittwoch": 2,
                "Donnerstag": 3,
                "Freitag": 4,
                "Samstag": 5,
                "Sonntag": 6,
            }
            return [
                weekday_map[day.strip()]
                for day in weekdays
                if day.strip() in weekday_map
            ]
        if key == "immediate_notifications":
            return line.strip().lower() == "ja"
        if key == "reminder_emails":
            return line.strip().lower() == "ja"
        return line

    def _find_line_starting_with_key(self, key: str, lines: List[str]) -> str:
        matching_lines = [line for line in lines if line.startswith(f"{key}:")]
        if len(matching_lines) > 1:
            logging.warning(f"Multiple lines found for key {key} in content")
            raise ValueError(
                f"Multiple lines for key {key} in subscription update content"
            )
        if len(matching_lines) == 0:
            if key in OPTIONAL_SUBSCRIPTION_UPDATE_KEYS:
                return ""
            else:
                logging.warning(f"Could not find line for key {key} in content")
                raise ValueError(f"Missing key {key} in subscription update content")
        return matching_lines[0].split(":", 1)[1].strip()


def assert_is_string(value: SUBSCRIPTION_META_VALUE_TYPES) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Expected a string value, but got {type(value)}")
    return value


def assert_is_boolean(value: SUBSCRIPTION_META_VALUE_TYPES) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"Expected a boolean value, but got {type(value)}")
    return value


def assert_is_integer_or_none(value: SUBSCRIPTION_META_VALUE_TYPES) -> Optional[int]:
    if value is None:
        return value
    if not isinstance(value, int):
        raise ValueError(f"Expected an integer value or None, but got {type(value)}")
    return value


def assert_is_list_of_integers(value: SUBSCRIPTION_META_VALUE_TYPES) -> List[int]:
    if not isinstance(value, list) or not all(isinstance(item, int) for item in value):
        raise ValueError(f"Expected a list of integers, but got {type(value)}")
    return value
