import logging
from typing import List
from O365.account import Account
from O365.message import Message
from src.utils.config import (
    SUBSCRIPTION_META_FILE,
)
from src.utils.email_processor_base import EmailProcessorBase
from src.utils.subscription_meta import (
    SubscriptionManager,
    SubscriptionMeta,
    SUBSCRIPTION_META_VALUE_TYPES,
)

OPTIONAL_SUBSCRIPTION_UPDATE_KEYS = ["weekdays"]


class SubscriptionUpdateEmailProcessor(EmailProcessorBase):
    def __init__(self, message: Message, account: Account):
        super().__init__(message, account)
        self.manager = SubscriptionManager(path=SUBSCRIPTION_META_FILE)

    def process(self) -> None:
        logging.info(
            f"... starting process for subscription update message {self.message.subject}"
        )
        content = self.message.body
        subscription_meta = self.get_subscription_meta_from_content(content)
        logging.info(f"... parsed subscription meta: {subscription_meta}")
        self.manager.add_or_update_subscription(subscription_meta)
        logging.info(f"... updated subscription for {subscription_meta.email}")
        logging.info(f"... done processing message {self.message.subject}")

    def get_subscription_meta_from_content(self, content: str) -> SubscriptionMeta:
        lines = content.splitlines()
        meta = {}
        for key in SubscriptionMeta.__annotations__.keys():
            value = self._extract_value_for_key_from_lines(key, lines)
            meta[key] = value
        return SubscriptionMeta(**meta)  # type: ignore[arg-type]

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
            return bool(int(line))
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
