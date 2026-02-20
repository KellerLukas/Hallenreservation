from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from pathlib import Path
import json
import tempfile
from typing import Dict, List, Optional, Union
from O365.account import Account
from src.config import SHAREPOINT_FOLDER_PATH, SHAREPOINT_SITE_ID

SUBSCRIPTION_META_VALUE_TYPES = Union[int, List[int], Optional[int], bool, str]
WEEKDAY_NAMES_DE = [
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
]


@dataclass
class SubscriptionMeta:
    email: str
    weekdays: List[int]
    reminder_lead_days: Optional[int] = None
    immediate_notifications: bool = False

    def __post_init__(self) -> None:
        if not all(0 <= d <= 6 for d in self.weekdays):
            raise ValueError("weekdays must be in range 0–6")
        if self.reminder_lead_days is not None and not (
            0 <= self.reminder_lead_days <= 30
        ):
            raise ValueError("reminder_lead_days must be between 0 and 30 or None")

    def to_dict(self) -> Dict[str, SUBSCRIPTION_META_VALUE_TYPES]:
        return asdict(self)

    def to_json(self, path: str | Path) -> None:
        path = Path(path)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_dict(
        cls, data: Dict[str, SUBSCRIPTION_META_VALUE_TYPES]
    ) -> "SubscriptionMeta":
        return cls(**data)  # type: ignore[arg-type]

    @classmethod
    def from_json(cls, path: str | Path) -> "SubscriptionMeta":
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


class SubscriptionManager:
    def __init__(self, path: str) -> None:
        self.path = path
        self._subscription_metas = self.load_subscriptions(path)

    def push_metas_to_sharepoint(self, account: Account) -> None:
        logging.info("Pushing subscription metas to SharePoint...")
        sharepoint = account.sharepoint()
        site = sharepoint.get_site(SHAREPOINT_SITE_ID)
        drive = site.get_default_document_library()
        try:
            folder = drive.get_item_by_path(SHAREPOINT_FOLDER_PATH)
        except Exception as e:
            raise RuntimeError(
                f"Could not access SharePoint folder at path {SHAREPOINT_FOLDER_PATH}: {e}"
            )
        target_file_name = "subscription_metas.txt"
        pretty_content = self.pretty_print_subscriptions()
        with tempfile.TemporaryDirectory() as temp_dir:
            upload_path = Path(temp_dir) / target_file_name
            upload_path.write_text(pretty_content, encoding="utf-8")
            new_file = folder.upload_file(str(upload_path), target_file_name)
        logging.info(
            f"... uploaded subscription metas to SharePoint file {new_file.name} to folder {folder.name}"
        )

    @property
    def subscription_metas(self) -> Dict[str, SubscriptionMeta]:
        return self._subscription_metas

    @property
    def max_lead_days(self) -> int:
        if not self.subscription_metas:
            return -1
        lead_days = [
            meta.reminder_lead_days
            for meta in self.subscription_metas.values()
            if meta.reminder_lead_days is not None
        ]
        if not lead_days:
            return -1
        return max(lead_days)

    @property
    def emails_per_lead_day_number_with_reminder_due_today(
        self,
    ) -> Dict[int, List[str]]:
        result = {}
        for n in range(self.max_lead_days + 1):
            emails = self.emails_with_reminders_due_today_for_event_in_n_days(n=n)
            if emails:
                result[n] = emails
        return result

    @staticmethod
    def load_subscriptions(path: str | Path) -> Dict[str, SubscriptionMeta]:
        path = Path(path)
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return {key: SubscriptionMeta.from_dict(value) for key, value in data.items()}

    @staticmethod
    def dump_subscriptions(subs: Dict[str, SubscriptionMeta], path: str | Path) -> None:
        path = Path(path)
        with path.open("w", encoding="utf-8") as f:
            json.dump(
                {key: value.to_dict() for key, value in subs.items()}, f, indent=2
            )

    def dump_to_file(self) -> None:
        self.dump_subscriptions(self._subscription_metas, self.path)

    def add_or_update_subscription(self, meta: SubscriptionMeta) -> None:
        self._subscription_metas[meta.email] = meta
        self.dump_to_file()

    def remove_subscription(self, email: str) -> None:
        if email in self._subscription_metas:
            del self._subscription_metas[email]
            self.dump_to_file()

    def emails_with_notifications_for_weekday(self, weekday: int) -> List[str]:
        return [
            meta.email
            for meta in self.subscription_metas.values()
            if weekday in meta.weekdays and meta.immediate_notifications
        ]

    def emails_with_reminders_due_today_for_event_in_n_days(self, n: int) -> List[str]:
        current_weekday = datetime.now().weekday()
        target_weekday = (current_weekday + n) % 7
        return [
            meta.email
            for meta in self.subscription_metas.values()
            if target_weekday in meta.weekdays and meta.reminder_lead_days == n
        ]

    def pretty_print_subscriptions(self) -> str:
        lines: List[str] = []
        for email, meta in self.subscription_metas.items():
            weekday_names = ", ".join(WEEKDAY_NAMES_DE[day] for day in meta.weekdays)
            lines.extend(
                [
                    email,
                    f"  Weekdays: {weekday_names}",
                    f"  Immediate Notifications: {meta.immediate_notifications}",
                    f"  Reminder Lead Days: {meta.reminder_lead_days}",
                    "",
                ]
            )

        result = "\n".join(lines).rstrip() + "\n"
        print(result, end="")
        return result
