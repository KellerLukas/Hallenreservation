from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import html
import json
import logging
import os
from typing import Dict, List
from O365 import Account
from O365.drive import File
from tempfile import TemporaryDirectory
from src.utils.find_attachment_meta import get_date_string_from_date
from src.utils.reservation_email_processor import get_reservations_folder
from src.utils.config import (
    DEFAULT_FROM_ADDRESS,
    REMINDER_PREFIX,
    SUBSCRIPTION_MANAGE_URL,
    SUPPORT_EMAIL_ADDRESS,
)
from src.utils.template.reminder_email_template import (
    template as reminder_email_template,
)
from src.utils.template.reminder_email_template import (
    reservation_list_template as reminder_email_reservation_list_template,
)

EMAIL_NEWLINE_STR = "\n<br>\n"


@dataclass
class SubscriptionMeta:
    email: str
    weekdays: List[int]
    lead_days: int

    def __post_init__(self):
        if not all(0 <= d <= 6 for d in self.weekdays):
            raise ValueError("weekdays must be in range 0–6")
        if self.lead_days < 0:
            raise ValueError("lead_days must be >= 0")

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: str | Path) -> None:
        path = Path(path)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "SubscriptionMeta":
        return cls(**data)

    @classmethod
    def from_json(cls, path: str | Path) -> "SubscriptionMeta":
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


def dump_subscriptions(subs: Dict[SubscriptionMeta], path: str | Path) -> None:
    path = Path(path)
    with path.open("w", encoding="utf-8") as f:
        json.dump({key: value.to_dict() for key, value in subs.items()}, f, indent=2)


def load_subscriptions(path: str | Path) -> Dict[str, SubscriptionMeta]:
    path = Path(path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {key: SubscriptionMeta.from_dict(value) for key, value in data.items()}


class ReservationReminder:
    def __init__(self, account: Account):
        self.account = account

    def remind_about_reservations_in_n_days(self, n: int, recipients: List[str]):
        logging.info(f"Reminding about reservations in {n} days: {recipients} ...")
        today = datetime.now()
        target_day = today + timedelta(days=n)
        reservations_on_date = self.get_reservations_on_date(target_day)
        if len(reservations_on_date) == 0:
            logging.info(
                f"... no reservations found on date {target_day.strftime('%d.%m.%Y')}"
            )
            return
        logging.info(
            f"... found {len(reservations_on_date)} reservations on date {target_day.strftime('%d.%m.%Y')}"
        )
        return self.send_reminder_email(
            reservations=reservations_on_date,
            date=target_day,
            recipients=recipients,
            n=n,
        )

    def get_reservations_on_date(self, date: datetime) -> Dict[str, File]:
        target_string = get_date_string_from_date(date)
        folder = get_reservations_folder(account=self.account, year=date.year)
        files = {item.name: item for item in folder.get_items()}
        matching_files = {
            filename: file
            for filename, file in files.items()
            if target_string in filename
        }
        return matching_files

    def send_reminder_email(
        self,
        reservations: Dict[str, File],
        date: datetime,
        recipients: List[str],
        n: int,
    ):
        logging.info("... sending email ...")
        mailbox = self.account.mailbox(resource=DEFAULT_FROM_ADDRESS)
        msg = mailbox.new_message()

        msg.subject = f"{REMINDER_PREFIX} Reservation vom {datetime.strftime(date, '%A, %d.%m.%Y')}"
        reservation_rows = "\n".join(
            reminder_email_reservation_list_template.format(
                filename=html.escape(filename)
            )
            for filename in reservations.keys()
        )
        text = reminder_email_template.format(
            days=n,
            date=datetime.strftime(date, "%A, %d.%m.%Y"),
            reservations=reservation_rows,
            subscription_manage_url=SUBSCRIPTION_MANAGE_URL,
            support_email_address=SUPPORT_EMAIL_ADDRESS,
        )

        msg.body = text
        msg.reply_to.add(SUPPORT_EMAIL_ADDRESS)
        for recipient in recipients:
            msg.bcc.add(recipient)

        logging.info("... downloading attachments ...")
        with TemporaryDirectory() as td:
            for filename, item in reservations.items():
                if not item:
                    continue
                item.download(to_path=td, name=filename)
                local_path = os.path.join(td, filename)
                msg.attachments.add(local_path)

            logging.info("... sending email ...")
            if not msg.send():
                raise ValueError("failed to send email!")
            logging.info("... email sent.")
