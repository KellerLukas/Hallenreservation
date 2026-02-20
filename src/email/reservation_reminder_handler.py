from datetime import datetime, timedelta
import logging
from typing import Dict, List
from O365.account import Account
from O365.drive import File
from src.email.email_sender import EmailSender
from src.utils.find_attachment_meta import get_date_string_from_date
from src.email.email_processors.reservation_email_processor import (
    get_reservations_folder,
)
from src.utils.typed_o365 import _get_items


class ReservationReminderHandler:
    def __init__(self, account: Account):
        self.account = account
        self.email_sender = EmailSender(account=account)

    def remind_about_reservations_in_n_days(
        self, n: int, recipients: List[str]
    ) -> None:
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
        return self.email_sender.send_reminder_email(
            reservations=reservations_on_date,
            date=target_day,
            recipients=recipients,
        )

    def get_reservations_on_date(self, date: datetime) -> Dict[str, File]:
        target_string = get_date_string_from_date(date)
        folder = get_reservations_folder(
            account=self.account, year=date.year, redacted=True
        )
        files = {item.name: item for item in _get_items(folder)}
        matching_files = {
            filename: file
            for filename, file in files.items()
            if target_string in filename
        }
        return matching_files
