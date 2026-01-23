import pandas as pd
from openai import OpenAI
import logging
import re
from typing import List, Optional
from pydantic import BaseModel

from src.utils.find_attachment_meta_prompt import (
    prompt_template as attachment_prompt_tmeplate,
)
from src.utils.find_attachment_meta_prompt import (
    question_template as attachment_question_template,
)
from src.utils.errors import ClassificationError
from src.utils.credentials import get_credentials_from_env_var
from src.utils.config import OPEN_AI_API_KEY_ENV_VAR


class AttachmentMeta(BaseModel):
    clean_filename: Optional[str]
    year: Optional[int]
    explain: Optional[str] = None


class FindAttachmentMeta:
    def __init__(self, message_body: str, message_subject: str) -> None:
        self.message_body = message_body
        self.message_subject = message_subject
        self.client = OpenAI(api_key=self.__get_key())

    def find(
        self, attachment_name: str, attachment_content: str
    ) -> List[AttachmentMeta]:
        try:
            org = self._find_organization(attachment_content)
            dates = self._find_dates(attachment_content)
        except ClassificationError:
            logging.warning(
                "Failed to classify attachment content conventionally. Using OpenAI fallback."
            )
            return self.find_using_openai(attachment_name, attachment_content)

        metas = []
        for date in dates:
            clean_filename = (
                "Reservation_{date.year}_{date.month:02d}_{date.day:02d}_{org}.pdf"
            )
            metas.append(
                AttachmentMeta(
                    clean_filename=clean_filename.format(date=date, org=org),
                    year=date.year,
                )
            )
        return metas

    def _find_organization(self, attachment_content: str) -> Optional[str]:
        booking_id = self._find_booking_id(attachment_content)
        if booking_id is None:
            raise ClassificationError("No booking ID found!")
        if booking_id + "\n" != attachment_content[: len(booking_id) + 1]:
            logging.warning(
                f"Booking ID {booking_id} does not match start of attachment content!"
            )
            raise ClassificationError(
                "Booking ID does not match start of attachment content!"
            )
        return attachment_content[len(booking_id) + 1 :].splitlines()[0]

    def _find_booking_id(self, attachment_content: str) -> Optional[str]:
        match = re.search(
            r"Definitive Buchungsbestätigung \((\d+)\)", attachment_content
        )
        if match:
            booking_id = match.group(1)
            return booking_id
        logging.warning("No booking ID found!")
        return None

    def _find_dates(self, attachment_content: str) -> List[pd.Timestamp]:
        subsequences = re.findall(
            r"Mietoptionen(.*?)Kosten", attachment_content, re.DOTALL
        )
        found_dates = []
        for subseq in subsequences:
            dates = re.findall(r"\b\d{2}\.\d{2}\.\d{4}\b", subseq)
            found_dates.extend(dates)
        if len(found_dates) == 0:
            logging.warning("No dates found!")
            raise ClassificationError("No dates found!")
        unique_dates = list(set(found_dates))
        return pd.to_datetime(unique_dates, format="%d.%m.%Y").tolist()

    def find_using_openai(
        self, attachment_name: str, attachment_content: str
    ) -> List[AttachmentMeta]:
        prompt = self._setup_prompt(
            attachment_name=attachment_name, attachment_content=attachment_content
        )
        question = attachment_question_template.format()
        response = self.client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            response_format=AttachmentMeta,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": question},
            ],
        )
        response = response.choices[0].message.parsed

        response.clean_filename = (
            response.clean_filename if not is_none(response.clean_filename) else None
        )

        if response.clean_filename is None:
            message = f"Could not find clean filename for attachment {attachment_name}, reason : {response.explain}"
            logging.warning(message)
            raise ClassificationError(message)
        if response.year is None:
            message = f"Could not find year for for attachment {attachment_name}, reason : {response.explain}"
            logging.warning(message)
            raise ClassificationError(message)

        logging.info(
            f"Found meta {response.clean_filename}, year {response.year} for for attachment {attachment_name}"
        )
        return [response]

    def _setup_prompt(self, attachment_name: str, attachment_content: str) -> str:
        template = attachment_prompt_tmeplate
        prompt = template.format(
            mail_body=self.message_body,
            mail_subject=self.message_subject,
            attachment_name=attachment_name,
            attachment_content=attachment_content,
        )
        return prompt

    def __get_key(self):
        return get_credentials_from_env_var(OPEN_AI_API_KEY_ENV_VAR)


def is_none(value):
    if value is None:
        return True
    if isinstance(value, str) and value.lower() == "none":
        return True
    return False
