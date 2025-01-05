import base64
import fitz
import tempfile
import logging
from O365 import Account
from O365.message import Message, MessageAttachment
from io import BytesIO
from src.utils.find_attachment_meta import AttachmentMeta, FindAttachmentMeta
from src.utils.config import SHAREPOINT_FOLDER_PATH, SHAREPOINT_SITE_ID


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
        pdf_document = fitz.open(stream=pdf_buffer, filetype="pdf")
        pdf_text = ""
        for page_num in range(pdf_document.page_count):
            page = pdf_document.load_page(page_num)
            pdf_text += page.get_text()

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

        new_file = folder.upload_file(temp_file_path, meta.clean_filename)
        logging.info(f"Uploaded file: {new_file.name}")
