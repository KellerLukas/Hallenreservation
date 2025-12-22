import base64
import re
from typing import Optional, Tuple
import PyPDF2
import tempfile
import logging
import numpy as np
from O365 import Account
from O365.message import Message, MessageAttachment
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
        logging.info(f"... done processing message {self.message.subject}")

    def process_attachment(self, attachment: MessageAttachment):
        logging.info(f"processing attachment {attachment.name}...")
        if not attachment.name.endswith(".pdf"):
            logging.info(f"... not a pdf")
            return None

        pdf_content = base64.b64decode(attachment.content)
        pdf_buffer = BytesIO(pdf_content)
        pdf_reader = PyPDF2.PdfReader(pdf_buffer)
        pdf_text = ""
        expected_num_of_pages = np.inf
        for page_num in range(len(pdf_reader.pages)):
            if page_num > expected_num_of_pages:
                logging.info(f"... stopping reading pdf {attachment.name} at page {page_num} due to expected number of pages {expected_num_of_pages}")
                break
            page = pdf_reader.pages[page_num]
            page_text = page.extract_text()
            pdf_text += page_text
            if page_num == 0:
                assumed_current_page, assumed_expected_num_of_pages = self.extract_page_number_from_pdf_text(page_text)
                if assumed_current_page is not None and assumed_expected_num_of_pages is not None:
                    if assumed_current_page != page_num:
                        logging.warning(
                            f"Page number mismatch in {attachment.name}: "
                            f"assumed current page {assumed_current_page}, "
                            f"actual page {page_num}"
                        )
                        continue
                    expected_num_of_pages = assumed_expected_num_of_pages

        meta = self.find_attachment_meta.find(
            attachment_name=attachment.name, attachment_content=pdf_text
        )
        self.upload_to_sharepoint(pdf_buffer=pdf_buffer, meta=meta)

    def get_attachments(self) -> list[MessageAttachment]:
        if not self.message.has_attachments:
            return []
        self.message.attachments.download_attachments()
        return [att for att in self.message.attachments]

    def upload_to_sharepoint(self, pdf_buffer: BytesIO, meta: AttachmentMeta):
        logging.info("... uploading to sharepoint")
        sharepoint = self.account.sharepoint()
        site = sharepoint.get_site(SHAREPOINT_SITE_ID)
        drive = site.get_default_document_library()

        folder_path = f"{SHAREPOINT_FOLDER_PATH}/{str(meta.year)}"
        try:
            folder = drive.get_item_by_path(folder_path)
        except Exception:
            folder = drive.create_folder(folder_path)
            logging.info(f"Created folder: {folder_path}")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(pdf_buffer.getvalue())
            temp_file_path = temp_file.name

        existing_files = [item.name for item in folder.get_items()]
        if meta.clean_filename in existing_files:
            base_name, ext = meta.clean_filename.rsplit('.', 1)
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
    def extract_page_number_from_pdf_text(pdf_text: str) -> Tuple[Optional[int], Optional[int]]:
            match = PAGE_NUMBER_REGEX.search(pdf_text)
            if match:
                return int(match.group(1)) - 1 , int(match.group(2)) - 1
            return None, None
