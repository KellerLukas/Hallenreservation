import base64
import re
from typing import List, Optional, Tuple
import PyPDF2
import tempfile
import logging
from O365 import Account
from O365.message import Message, MessageAttachment
from O365.drive import Folder
from io import BytesIO
from src.utils.find_attachment_meta import AttachmentMeta, FindAttachmentMeta
from src.utils.config import SHAREPOINT_FOLDER_PATH, SHAREPOINT_SITE_ID

PAGE_NUMBER_REGEX = re.compile(r"Seite (\d+)/(\d+)")


class EmailProcessor:
    def __init__(self, message: Message, account: Account):
        self.message = message
        self.account = account
        self.find_attachment_meta = FindAttachmentMeta(
            message_body=self.message.body, message_subject=self.message.subject
        )

    def process(self):
        logging.info(f"Processing message {self.message.subject}")

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

    def process_attachment(self, attachment: MessageAttachment):
        logging.info(f"processing attachment {attachment.name}...")
        if not attachment.name.endswith(".pdf"):
            logging.info("... not a pdf")
            return None

        pdf_content = base64.b64decode(attachment.content)
        pdf_buffer = BytesIO(pdf_content)
        pdf_reader = PyPDF2.PdfReader(pdf_buffer)
        cutoff_page_num = self.determine_pdf_cutoff(pdf_reader=pdf_reader)
        if cutoff_page_num:
            pdf_reader = self.cut_pdf_reader_after_page_n(
                pdf_reader=pdf_reader, n=cutoff_page_num
            )
        else:
            logging.warning("No cutoff page number detected!")
        pdf_text = self.read_pdf(pdf_reader)

        metas = self.find_attachment_meta.find(
            attachment_name=attachment.name, attachment_content=pdf_text
        )
        self.upload_to_sharepoint(pdf_reader=pdf_reader, metas=metas)

    def read_pdf(self, reader: PyPDF2.PdfReader) -> str:
        pdf_text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            pdf_text += page_text
        return pdf_text

    def determine_pdf_cutoff(self, pdf_reader: PyPDF2.PdfReader) -> Optional[int]:
        first_page = pdf_reader.pages[0]
        page_text = first_page.extract_text()
        detected_current_page, detected_expected_num_of_pages = (
            self.extract_page_number_from_pdf_text(page_text)
        )
        if detected_current_page is None or detected_expected_num_of_pages is None:
            return None
        if detected_current_page != 0:
            logging.warning(
                f"Page number mismatch: assumed current page {detected_current_page}, "
                f"actual page 0"
            )
            return None
        return detected_expected_num_of_pages

    def get_attachments(self) -> list[MessageAttachment]:
        if not self.message.has_attachments:
            return []
        self.message.attachments.download_attachments()
        return [att for att in self.message.attachments]

    def upload_to_sharepoint(
        self, pdf_reader: PyPDF2.PdfReader, metas: List[AttachmentMeta]
    ):
        logging.info("... uploading to sharepoint")

        for meta in metas:
            self.upload_single_file_to_sharepoint(pdf_reader, meta)

    def upload_single_file_to_sharepoint(
        self, pdf_reader: PyPDF2.PdfReader, meta: AttachmentMeta
    ):
        folder = get_reservations_folder(account=self.account, year=meta.year)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(pdf_reader.stream.getvalue())
            temp_file_path = temp_file.name

        existing_files = [item.name for item in folder.get_items()]
        if meta.clean_filename in existing_files:
            base_name, ext = meta.clean_filename.rsplit(".", 1)
            suffix = 1
            while True:
                new_filename = f"{base_name}_{suffix}.{ext}"
                if new_filename not in existing_files:
                    meta.clean_filename = new_filename
                    break
                suffix += 1
        new_file = folder.upload_file(temp_file_path, meta.clean_filename)
        logging.info(f"Uploaded file: {new_file.name}")

    @staticmethod
    def extract_page_number_from_pdf_text(
        pdf_text: str,
    ) -> Tuple[Optional[int], Optional[int]]:
        match = PAGE_NUMBER_REGEX.search(pdf_text)
        if match:
            return int(match.group(1)) - 1, int(match.group(2))
        return None, None

    @staticmethod
    def cut_pdf_reader_after_page_n(
        pdf_reader: PyPDF2.PdfReader, n: int
    ) -> PyPDF2.PdfReader:
        pdf_writer = PyPDF2.PdfWriter()
        for page_num in range(min(n, len(pdf_reader.pages))):
            pdf_writer.add_page(pdf_reader.pages[page_num])

        output_buffer = BytesIO()
        pdf_writer.write(output_buffer)
        output_buffer.seek(0)

        return PyPDF2.PdfReader(output_buffer)


def get_reservations_folder(account: Account, year: int) -> Folder:
    year_str = str(year)
    sharepoint = account.sharepoint()
    site = sharepoint.get_site(SHAREPOINT_SITE_ID)
    drive = site.get_default_document_library()

    folder_path = f"{SHAREPOINT_FOLDER_PATH}/{year_str}"
    try:
        parent = drive.get_item_by_path(SHAREPOINT_FOLDER_PATH)
    except Exception:
        raise RuntimeError(f"Base path does not exist: {SHAREPOINT_FOLDER_PATH}")
    try:
        folder = drive.get_item_by_path(folder_path)
    except Exception:
        folder = parent.create_child_folder(year_str)
        logging.info(f"Created folder: {folder_path}")
    return folder
