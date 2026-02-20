import fitz
import html
import logging
import os
import traceback
from typing import Dict, List
from datetime import datetime
from O365.message import Message
from O365.account import Account
from O365.drive import File

from tempfile import TemporaryDirectory
from src.utils.config import (
    DEFAULT_FROM_ADDRESS,
    NOTIFICATION_PREFIX,
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
from src.utils.typed_o365 import _forward_message, _send_message, _set_message_body
from src.utils.typed_pymupdf import _save_pdf


EMAIL_NEWLINE_STR = "\n<br>\n"


class EmailSendingError(Exception):
    pass


class EmailSender:
    def __init__(self, account: Account):
        self.account = account
        self.mailbox = self.account.mailbox(resource=DEFAULT_FROM_ADDRESS)

    def send_alert_message_for_upload(self, message: Message, issue: Exception) -> None:
        subject = f"HALLENRESERVATION UPLOAD ERROR: {message.subject}"
        body = str(issue) + EMAIL_NEWLINE_STR + traceback.format_exc()
        return self._forward_email(
            message=message,
            subject=subject,
            additional_body=body,
            recipients=[SUPPORT_EMAIL_ADDRESS],
        )

    def send_alert_message_for_reminder(self, issue: Exception) -> None:
        subject = "HALLENRESERVATION REMINDER ERROR"
        body = str(issue) + EMAIL_NEWLINE_STR + traceback.format_exc()
        return self._send_email(
            subject=subject,
            body=body,
            recipients=[SUPPORT_EMAIL_ADDRESS],
            attachments=[],
        )

    def send_alert_message_for_subscription_update(
        self, message: Message, issue: Exception
    ) -> None:
        subject = f"HALLENRESERVATION SUBSCRIPTION UPDATE ERROR: {message.subject}"
        body = str(issue) + EMAIL_NEWLINE_STR + traceback.format_exc()
        return self._forward_email(
            message=message,
            subject=subject,
            additional_body=body,
            recipients=[SUPPORT_EMAIL_ADDRESS],
        )

    def send_reminder_email(
        self,
        reservations: Dict[str, File],
        date: datetime,
        recipients: List[str],
    ) -> None:
        subject = f"{REMINDER_PREFIX} Reservation vom {datetime.strftime(date, '%A, %d.%m.%Y')}"
        reservation_rows = "\n".join(
            reminder_email_reservation_list_template.format(
                filename=html.escape(filename)
            )
            for filename in reservations.keys()
        )
        text = reminder_email_template.format(
            days=(date - datetime.now()).days,
            date=datetime.strftime(date, "%A, %d.%m.%Y"),
            reservations=reservation_rows,
            subscription_manage_url=SUBSCRIPTION_MANAGE_URL,
            support_email_address=SUPPORT_EMAIL_ADDRESS,
        )

        logging.info("... downloading attachments ...")
        attachments = []
        with TemporaryDirectory() as td:
            for filename, item in reservations.items():
                if item is None:
                    continue
                item.download(to_path=td, name=filename)
                local_path = os.path.join(td, filename)
                attachments.append(local_path)
            return self._send_email(
                subject=subject,
                body=text,
                recipients=recipients,
                attachments=attachments,
            )

    def send_immediate_notification_email(
        self,
        pdf_doc: fitz.Document,
        filename: str,
        date: datetime,
        recipients: List[str],
    ) -> None:
        subject = f"{NOTIFICATION_PREFIX} Reservation vom {datetime.strftime(date, '%A, %d.%m.%Y')}"
        body = f"Es gibt eine neue Reservation für den {datetime.strftime(date, '%A, %d.%m.%Y')}."
        with TemporaryDirectory() as td:
            attachment_path = os.path.join(td, filename)
            _save_pdf(pdf_doc, attachment_path)
            return self._send_email(
                subject=subject,
                body=body,
                recipients=recipients,
                attachments=[attachment_path],
            )

    def _send_email(
        self, subject: str, body: str, recipients: List[str], attachments: List[str]
    ) -> None:
        msg = self.mailbox.new_message()
        msg.subject = subject
        _set_message_body(msg, body)
        msg.reply_to.add(SUPPORT_EMAIL_ADDRESS)
        for recipient in recipients:
            msg.bcc.add(recipient)

        for attachment in attachments:
            msg.attachments.add(attachment)
        logging.info("... sending email ...")
        if not _send_message(msg):
            raise EmailSendingError("failed to send email!")
        logging.info("... email sent.")

    def _forward_email(
        self,
        message: Message,
        subject: str,
        additional_body: str,
        recipients: List[str],
    ) -> None:
        fwd = _forward_message(message)
        fwd.subject = subject
        _set_message_body(fwd, additional_body + EMAIL_NEWLINE_STR + fwd.body)
        for recipient in recipients:
            fwd.to.add(recipient)
        logging.info("... forwarding email ...")
        if not _send_message(fwd):
            raise EmailSendingError("failed to forward email!")
        logging.info("... email forwarded.")
