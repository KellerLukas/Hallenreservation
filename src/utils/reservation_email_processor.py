import base64
import os
import re
from typing import List, Optional, Set, Tuple
import fitz
import tempfile
import logging
from O365.account import Account
from O365.message import Message, MessageAttachment
from O365.drive import Folder, File
from tempfile import TemporaryDirectory
from src.utils.email_sender import EmailSender
from src.utils.find_attachment_meta import AttachmentMeta, FindAttachmentMeta
from src.utils.config import (
    SHAREPOINT_FOLDER_PATH,
    SHAREPOINT_FOLDER_PATH_REDACTED,
    SHAREPOINT_SITE_ID,
    SUBSCRIPTION_META_FILE,
)
from src.utils.email_processor_base import EmailProcessorBase
from src.utils.subscription_meta import SubscriptionManager
from src.utils.typed_o365 import _get_items
from src.utils.typed_pymupdf import (
    _insert_pdf,
    _open_empty_pdf,
    _open_pdf_from_bytes,
    _open_pdf_from_path,
    _pdf_tobytes,
)

PAGE_NUMBER_REGEX = re.compile(r"Seite (\d+)/(\d+)")


class ReservationEmailProcessor(EmailProcessorBase):
    def __init__(self, message: Message, account: Account):
        super().__init__(message, account)
        self.find_attachment_meta = FindAttachmentMeta()
        self.manager = SubscriptionManager(path=SUBSCRIPTION_META_FILE)
        self.email_sender = EmailSender(account=self.account)

    def process(self) -> None:
        logging.info(
            f"... starting process for reservation message {self.message.subject}"
        )

        attachments = self.get_attachments()
        for attachment in attachments:
            try:
                self.process_attachment(attachment)
            except Exception as e:
                # ToDo: handle this better: distinguish different exceptions and add retry
                logging.warning(f"Error processing attachment {attachment.name}")
                logging.warning(e)
                raise e
        logging.info(f"... done processing message {self.message.subject}")

    def process_attachment(self, attachment: MessageAttachment) -> None:
        logging.info(f"... processing attachment {attachment.name}...")
        if not isinstance(attachment.name, str):
            raise ValueError(f"Attachment name is not a string: {attachment.name}")
        if not attachment.name.endswith(".pdf"):
            logging.info("... not a pdf")
            return
        if not isinstance(attachment.content, str):
            raise ValueError(
                f"Unexpected attachment content type: {type(attachment.content)}"
            )
        pdf_content = base64.b64decode(attachment.content)
        pdf_doc = _open_pdf_from_bytes(pdf_content)
        cutoff_page_num = self.determine_pdf_cutoff(pdf_doc=pdf_doc)
        if cutoff_page_num:
            pdf_doc = self.cut_pdf_after_page_n(pdf_doc=pdf_doc, n=cutoff_page_num)
        else:
            logging.warning("... no cutoff page number detected!")

        pdf_text = self.read_pdf(pdf_doc)
        metas = self.find_attachment_meta.find(attachment_content=pdf_text)
        if not metas:
            raise ValueError(
                f"Could not find meta information for attachment {attachment.name}"
            )
        self.upload_to_sharepoint(pdf_doc=pdf_doc, metas=metas, redacted=False)
        sensitive_content = metas[0].sensitive_content
        pdf_doc_redacted = self.redact_pdf(
            pdf_doc=pdf_doc, strings_to_redact=sensitive_content
        )
        self.upload_to_sharepoint(pdf_doc=pdf_doc_redacted, metas=metas, redacted=True)
        weekdays = {meta.date.weekday() for meta in metas}
        emails_to_notify = set()
        for weekday in weekdays:
            emails_to_notify.update(
                self.manager.emails_with_notifications_for_weekday(weekday)
            )
        if not emails_to_notify:
            logging.info(
                f"... no immediate notifications to send for attachment {attachment.name}"
            )
            return
        logging.info(
            f"... sending immediate notifications to {emails_to_notify} for attachment {attachment.name}"
        )
        self.email_sender.send_immediate_notification_email(
            pdf_doc=pdf_doc_redacted,
            filename=metas[0].clean_filename,
            date=metas[0].date,
            recipients=list(emails_to_notify),
        )

    def read_pdf(self, doc: fitz.Document) -> str:
        pdf_text = ""
        for page in doc:  # type: ignore[attr-defined]
            page_text = page.get_text()
            pdf_text += page_text
        return pdf_text

    def determine_pdf_cutoff(self, pdf_doc: fitz.Document) -> Optional[int]:
        first_page = pdf_doc[0]
        page_text = first_page.get_text()  # type: ignore[attr-defined]
        detected_current_page, detected_expected_num_of_pages = (
            self.extract_page_number_from_pdf_text(page_text)
        )
        if detected_current_page is None or detected_expected_num_of_pages is None:
            return None
        if detected_current_page != 0:
            logging.warning(
                f"... page number mismatch: assumed current page {detected_current_page}, actual page 0"
            )
            return None
        return detected_expected_num_of_pages

    def redact_pdf(
        self, pdf_doc: fitz.Document, strings_to_redact: Set[str]
    ) -> fitz.Document:
        redacted_doc = _open_empty_pdf()
        _insert_pdf(redacted_doc, pdf_doc)

        for page in redacted_doc:  # type: ignore[attr-defined]
            for str_to_redact in strings_to_redact:
                text_instances = page.search_for(str_to_redact)
                for inst in text_instances:
                    page.add_redact_annot(
                        inst, fill=(0, 0, 0)
                    )  # RGB (0,0,0) = black bar
            page.apply_redactions()
        return redacted_doc

    def get_attachments(self) -> list[MessageAttachment]:
        if not self.message.has_attachments:
            return []
        self.message.attachments.download_attachments()
        return [att for att in self.message.attachments]

    def upload_to_sharepoint(
        self, pdf_doc: fitz.Document, metas: List[AttachmentMeta], redacted: bool
    ) -> None:
        logging.info(
            f"... uploading to sharepoint {'in redacted form' if redacted else ''}..."
        )
        for meta in metas:
            self.upload_single_file_to_sharepoint(pdf_doc, meta, redacted)

    def upload_single_file_to_sharepoint(
        self, pdf_doc: fitz.Document, meta: AttachmentMeta, redacted: bool
    ) -> None:
        folder = get_reservations_folder(
            account=self.account, year=meta.date.year, redacted=redacted
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(_pdf_tobytes(pdf_doc))
            temp_file_path = temp_file.name

        try:
            existing_files = [item for item in _get_items(folder)]
            if meta.clean_filename in {item.name for item in existing_files}:
                base_name, ext = meta.clean_filename.rsplit(".", 1)
                existing_files_matching_base_name = [
                    item for item in existing_files if item.name.startswith(base_name)
                ]
                for file in existing_files_matching_base_name:
                    if self._sp_file_identical_to_local(file, temp_file_path):
                        logging.info(
                            f"... file with identical content already exists: {file.name}, skipping upload"
                        )
                        return
                existing_suffixes = [
                    name[len(base_name) + 1 : -len(ext) - 1]
                    for name in {
                        item.name for item in existing_files_matching_base_name
                    }
                ]
                if "" in existing_suffixes:
                    existing_suffixes.remove("")
                existing_suffixes = [int(suffix) for suffix in existing_suffixes]
                new_suffix = max(existing_suffixes) + 1 if existing_suffixes else 1
                meta.clean_filename = f"{base_name}_{new_suffix}.{ext}"
            new_file = folder.upload_file(temp_file_path, meta.clean_filename)
            logging.info(f"... uploaded file: {new_file.name} to folder: {folder.name}")
        finally:
            try:
                os.remove(temp_file_path)
            except FileNotFoundError:
                pass
            except OSError as cleanup_error:
                logging.warning(
                    f"... failed to delete temporary file {temp_file_path}: {cleanup_error}"
                )

    def _sp_file_identical_to_local(self, sp_file: File, local_file_path: str) -> bool:
        with TemporaryDirectory() as td:
            sp_file.download(to_path=td, name=sp_file.name)
            sp_file_path = os.path.join(td, sp_file.name)
            return self._pdf_text_signature(
                local_file_path
            ) == self._pdf_text_signature(sp_file_path)

    @staticmethod
    def _pdf_text_signature(file_path: str) -> str:
        pages: List[str] = []
        with _open_pdf_from_path(file_path) as doc:
            for page in doc:
                pages.append(" ".join(page.get_text("text").split()))
        return f"{len(pages)}|" + "\f".join(pages)

    @staticmethod
    def extract_page_number_from_pdf_text(
        pdf_text: str,
    ) -> Tuple[Optional[int], Optional[int]]:
        match = PAGE_NUMBER_REGEX.search(pdf_text)
        if match:
            return int(match.group(1)) - 1, int(match.group(2))
        return None, None

    @staticmethod
    def cut_pdf_after_page_n(pdf_doc: fitz.Document, n: int) -> fitz.Document:
        new_doc = _open_empty_pdf()
        _insert_pdf(new_doc, pdf_doc, from_page=0, to_page=n - 1)
        return new_doc


def get_reservations_folder(account: Account, year: int, redacted: bool) -> Folder:
    year_str = str(year)
    sharepoint = account.sharepoint()
    site = sharepoint.get_site(SHAREPOINT_SITE_ID)
    drive = site.get_default_document_library()

    base_folder = (
        SHAREPOINT_FOLDER_PATH_REDACTED if redacted else SHAREPOINT_FOLDER_PATH
    )
    folder_path = f"{base_folder}/{year_str}"
    try:
        parent = drive.get_item_by_path(base_folder)
    except Exception:
        raise RuntimeError(f"Base path does not exist: {base_folder}")
    try:
        folder = drive.get_item_by_path(folder_path)
    except Exception:
        folder = parent.create_child_folder(year_str)
        logging.info(f"... created folder: {folder_path}")
    if not isinstance(folder, Folder):
        raise RuntimeError(f"Expected {folder_path} to be a folder!")
    return folder
