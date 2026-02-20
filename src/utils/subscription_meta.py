from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json
from typing import Dict, List, Optional, Union

SUBSCRIPTION_META_VALUE_TYPES = Union[int, List[int], Optional[int], bool, str]


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
