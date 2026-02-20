from typing import Iterable, Protocol, cast
from O365.message import Message
from O365.drive import File, Folder


class _MessageReadState(Protocol):
    def mark_as_read(self) -> None: ...

    def mark_as_unread(self) -> None: ...


def _mark_as_read(message: Message) -> None:
    cast(_MessageReadState, message).mark_as_read()


def _mark_as_unread(message: Message) -> None:
    cast(_MessageReadState, message).mark_as_unread()


class _MessageForward(Protocol):
    def forward(self) -> Message: ...


class _MessageSend(Protocol):
    def send(self) -> bool: ...


def _forward_message(message: _MessageForward) -> Message:
    return message.forward()


def _send_message(message: _MessageSend) -> bool:
    return message.send()


class _MessageBody(Protocol):
    body: str


def _set_message_body(message: Message, body: str) -> None:
    cast(_MessageBody, message).body = body


class _FolderItems(Protocol):
    def get_items(self) -> Iterable[File]: ...


def _get_items(folder: Folder) -> Iterable[File]:
    return cast(_FolderItems, folder).get_items()
