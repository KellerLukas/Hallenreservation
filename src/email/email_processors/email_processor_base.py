from O365.account import Account
from O365.message import Message


class EmailProcessorBase:
    def __init__(self, message: Message, account: Account):
        self.message = message
        self.account = account

    def process(self) -> None:
        raise NotImplementedError()
