from src.utils.credentials import get_o365_credentials_from_env
from src.utils.fixed_o365_account import FixedAccount

credentials = get_o365_credentials_from_env()
account = FixedAccount(credentials)

redirect_uri = "https://localhost:5000"
scopes = ["basic", "message_all_shared", "Sites.ReadWrite.All", "Files.ReadWrite.All"]
kwargs = {"redirect_uri": redirect_uri}


if not account.is_authenticated:
    consent_url = account.get_consent_url(scopes=scopes, redirect_uri=redirect_uri)
    print(consent_url)
else:
    print("Already Authenticated!")

# To reset:
# account.con.token_backend.delete_token()
