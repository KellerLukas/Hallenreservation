import logging
from O365 import Account
from O365.message import Message
from src.utils.config import (
    SUBSCRIPTION_META_FILE,
)
from src.utils.email_processor_base import EmailProcessorBase
from src.utils.reservation_reminder import (
    dump_subscriptions,
    load_subscriptions,
    SubscriptionMeta,
)


class SubscriptionUpdateEmailProcessor(EmailProcessorBase):
    def __init__(self, message: Message, account: Account):
        super().__init__(message, account)
        self.subscriptions = load_subscriptions(SUBSCRIPTION_META_FILE)

    def process(self):
        logging.info(
            f"... starting process for subscription update message {self.message.subject}"
        )
        content = self.message.body
        subscription_meta = self.get_subscription_meta_from_content(content)
        logging.info(f"... parsed subscription meta: {subscription_meta}")

        if subscription_meta.weekdays == []:
            if subscription_meta.email in self.subscriptions:
                del self.subscriptions[subscription_meta.email]
                logging.info(f"... removed subscription for {subscription_meta.email}")
            else:
                logging.info(
                    f"... no existing subscription for {subscription_meta.email} to remove"
                )
            return

        self.subscriptions[subscription_meta.email] = subscription_meta
        logging.info(f"... updated subscription for {subscription_meta.email}")
        logging.info(f"... done processing message {self.message.subject}")
        dump_subscriptions(self.subscriptions, SUBSCRIPTION_META_FILE)

    def get_subscription_meta_from_content(self, content: str) -> SubscriptionMeta:
        lines = content.splitlines()
        meta = {}
        for key in SubscriptionMeta.__annotations__.keys():
            matching_lines = [line for line in lines if line.startswith(f"{key}:")]
            if len(matching_lines) == 1:
                value = matching_lines[0].split(":", 1)[1].strip()
            if len(matching_lines) > 1:
                logging.warning(f"Multiple lines found for key {key} in content")
                raise ValueError(
                    f"Multiple lines for key {key} in subscription update content"
                )
            if len(matching_lines) == 0:
                if key == "weekdays":
                    value = ""
                else:
                    logging.warning(f"Could not find line for key {key} in content")
                    raise ValueError(
                        f"Missing key {key} in subscription update content"
                    )

            if key == "lead_days":
                value = int(value)
            if key == "weekdays":
                weekdays = value.split(",")
                weekday_map = {
                    "Montag": 0,
                    "Dienstag": 1,
                    "Mittwoch": 2,
                    "Donnerstag": 3,
                    "Freitag": 4,
                    "Samstag": 5,
                    "Sonntag": 6,
                }
                value = [
                    weekday_map[day.strip()]
                    for day in weekdays
                    if day.strip() in weekday_map
                ]
            meta[key] = value
        return SubscriptionMeta(**meta)
