import os
import json
from src.utils.credentials import (
    setup_env_var_token,
    get_o365_credentials_from_op,
)
from src.utils.fixed_o365_account import FixedAccount

setup_env_var_token()
credentials = get_o365_credentials_from_op()
# credentials = get_o365_credentials_from_env()
account = FixedAccount(credentials)

redirect_uri = "https://localhost:5000"
scopes = ["basic", "message_all_shared", "Sites.ReadWrite.All", "Files.ReadWrite.All"]

temporary_flow_dump_file = "TEMP_flow.json"

TOKEN_URL = ""

if account.is_authenticated:
    print("Already Authenticated!")
else:
    flow = None
    if os.path.exists(temporary_flow_dump_file):
        with open(temporary_flow_dump_file, "r") as f:
            flow = json.load(f)
    if TOKEN_URL and flow:
        response = account.put_token_url(token_url=TOKEN_URL, flow=flow)
        print(response)
        os.remove(temporary_flow_dump_file)
    else:
        consent_url, flow = account.get_consent_url(
            requested_scopes=scopes, redirect_uri=redirect_uri
        )
        with open(temporary_flow_dump_file, "w") as f:
            json.dump(flow, f)
        print(
            "Go to this link, copy the redirected url, paste here as token_url and rerun script"
        )
        print(consent_url)


# To reset:
# account.con.token_backend.delete_token()
