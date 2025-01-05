from src.utils.credentials import get_credentials
from src.utils.fixed_o365_account import FixedAccount
from src.utils.manual_authentication.step_1 import redirect_uri

credentials = get_credentials()
account = FixedAccount(credentials)

token_url = ""  # enter token url here
account.put_token_url(token_url=token_url, redirect_uri=redirect_uri)
