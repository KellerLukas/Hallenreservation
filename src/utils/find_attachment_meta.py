from openai import OpenAI
import logging
from pydantic import BaseModel
from typing import Optional

<<<<<<< HEAD
from utils.find_attachment_meta_prompt import (
    prompt_template as attachment_prompt_tmeplate,
)
from utils.find_attachment_meta_prompt import (
=======
from src.utils.find_attachment_meta_prompt import (
    prompt_template as attachment_prompt_tmeplate,
)
from src.utils.find_attachment_meta_prompt import (
>>>>>>> 2777117c519a0f4f096b1384368fe8ca2c98e8bb
    question_template as attachment_question_template,
)
from src.utils.errors import ClassificationError
from src.utils.credentials import get_credentials_from_env_var
from src.utils.config import OPEN_AI_API_KEY_ENV_VAR


class AttachmentMeta(BaseModel):
    clean_filename: Optional[str]
    year: Optional[int]
    explain: Optional[str]


class FindAttachmentMeta:
    def __init__(self, message_body: str, message_subject: str) -> None:
        self.client = OpenAI(api_key=self.__get_key())
        self.message_body = message_body
        self.message_subject = message_subject

    def find(self, attachment_name: str, attachment_content: str) -> AttachmentMeta:
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
        return response

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
