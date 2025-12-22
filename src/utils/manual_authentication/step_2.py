from src.utils.credentials import get_o365_credentials_from_env
from src.utils.fixed_o365_account import FixedAccount
from src.utils.manual_authentication.step_1 import redirect_uri

credentials = get_o365_credentials_from_env()
account = FixedAccount(credentials)

token_url = ""  # enter token url here
account.put_token_url(token_url=token_url, redirect_uri=redirect_uri)
