import logging
import re
import unicodedata
from typing import List, Optional, Set, Any
from datetime import datetime
from pydantic import BaseModel

from src.utils.errors import ClassificationError

DATE_REGEX_STR = r"\b\d{2}\.\d{2}\.\d{4}\b"


class AttachmentMeta(BaseModel):
    clean_filename: str
    date: datetime
    sensitive_content: Set[str] = set()


class FindAttachmentMeta:
    def find(self, attachment_content: str) -> List[AttachmentMeta]:
        booking_id = self._find_booking_id(attachment_content)
        if not booking_id:
            logging.warning("Could not find booking ID in attachment content!")
            raise ClassificationError(
                "Could not find booking ID in attachment content!"
            )
        org = self._find_organization(attachment_content, booking_id=booking_id)
        dates = self._find_dates(attachment_content)
        sensitive_content = self._find_sensitive_content(attachment_content)
        sensitive_content = self._remove_string_from_sensitive_content(
            sensitive_content, ""
        )
        if org:
            sensitive_content = self._remove_string_from_sensitive_content(
                sensitive_content, org
            )
        metas = []
        for date in dates:
            clean_filename = (
                f"Reservation_{get_date_string_from_date(date)}_{org}_{booking_id}.pdf"
            )
            clean_filename = clean_filename_for_sharepoint(clean_filename)
            metas.append(
                AttachmentMeta(
                    clean_filename=clean_filename,
                    date=date,
                    sensitive_content=sensitive_content,
                )
            )
        return metas

    def _find_organization(
        self, attachment_content: str, booking_id: str
    ) -> Optional[str]:
        address_block = self._find_address_block(
            attachment_content, booking_id=booking_id
        )
        return address_block[0] if address_block else None

    def _find_address_block(
        self, attachment_content: str, booking_id: str
    ) -> List[str]:
        if booking_id + "\n" != attachment_content[: len(booking_id) + 1]:
            logging.warning(
                f"Booking ID {booking_id} does not match start of attachment content!"
            )
            raise ClassificationError(
                "Booking ID does not match start of attachment content!"
            )
        lines = attachment_content[len(booking_id) + 1 :].splitlines()
        address_block = []
        for line in lines:
            if booking_id in line:
                break
            address_block.append(line)
        if len(address_block) > 10:
            logging.warning(
                "Address block is too long! This might indicate an error in the detection."
            )
            raise ClassificationError("Address block is too long!")
        address_block = [line.strip() for line in address_block if line.strip()]
        address_block = [
            line for line in address_block if not re.search(DATE_REGEX_STR, line)
        ]
        return address_block

    def _find_booking_id(self, attachment_content: str) -> Optional[str]:
        matches = re.search(
            r"Buchungsbestätigung \((\d+)\)", attachment_content
        )  # Note: at least Defintivie Buchungsbestätigung as well as "Geänderte definitive Buchungsbestätigung" or "Provisorische Buchungsbestätigung" are possible
        if matches:
            booking_id = matches.group(1)
            return booking_id
        logging.warning("No booking ID found!")
        raise ClassificationError("No booking ID found!")

    def _find_dates(self, attachment_content: str) -> List[datetime]:
        subsequences = re.findall(
            r"Mietoptionen(.*?)Kosten", attachment_content, re.DOTALL
        )
        found_dates = []
        for subseq in subsequences:
            dates = re.findall(DATE_REGEX_STR, subseq)
            found_dates.extend(dates)
        if len(found_dates) == 0:
            logging.warning("No dates found!")
            raise ClassificationError("No dates found!")
        unique_dates = list(set(found_dates))
        return [datetime.strptime(date, "%d.%m.%Y") for date in unique_dates]

    def _find_sensitive_content(self, attachment_content: str) -> Set[str]:
        sensitive_content = set()
        sensitive_content.update(self._find_phone_numbers(attachment_content))
        sensitive_content.update(self._find_email_addresses(attachment_content))
        booking_id = self._find_booking_id(attachment_content)
        if booking_id:
            sensitive_content.update(
                set(self._find_address_block(attachment_content, booking_id=booking_id))
            )
        return sensitive_content

    def _remove_string_from_sensitive_content(
        self, sensitive_content: Set[str], string_to_remove: str
    ) -> Set[str]:
        if string_to_remove in sensitive_content:
            sensitive_content.remove(string_to_remove)
        return sensitive_content

    def _find_phone_numbers(self, attachment_content: str) -> Set[str]:
        phone_number_regex = (
            r"\+\d{1,2}\s??\(?\d{2,3}\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}"
        )
        phone_numbers = re.findall(phone_number_regex, attachment_content, re.MULTILINE)
        return set(phone_numbers)

    def _find_email_addresses(self, attachment_content: str) -> Set[str]:
        email_regex = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9_.-]+\.[a-zA-Z0-9-._]+"
        email_addresses = re.findall(email_regex, attachment_content)
        return set(email_addresses)


def is_none(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.lower() == "none":
        return True
    return False


def clean_filename_for_sharepoint(filename: str) -> str:
    """
    Cleans a filename to be compatible with SharePoint restrictions.
    Removes invalid characters and reserved names.

    Args:
        filename (str): The original filename

    Returns:
        str: The cleaned filename
    """
    cleaned = unicodedata.normalize("NFKC", filename)

    # Remove control characters (including null bytes)
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", cleaned)

    # Characters not allowed in SharePoint filenames
    invalid_chars = r'[<>:"/\\|?*]'

    # Remove invalid characters
    cleaned = re.sub(invalid_chars, "", cleaned)

    # Remove leading/trailing spaces and periods
    cleaned = cleaned.strip(". ")

    # Replace multiple spaces with single space
    cleaned = re.sub(r"\s+", " ", cleaned)

    # Remove reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    reserved = r"^(CON|PRN|AUX|NUL|COM\d|LPT\d)(?:\.|$)"
    if re.match(reserved, cleaned, re.IGNORECASE):
        cleaned = f"_{cleaned}"

    # Limit length to 255 characters (SharePoint limit)
    cleaned = cleaned[:255]

    return cleaned


def get_date_string_from_date(date: datetime) -> str:
    return f"{date.year}_{date.month:02d}_{date.day:02d}"
