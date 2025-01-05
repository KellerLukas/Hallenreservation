import os
import logging
from typing import Tuple
from src.utils.improved_onepassword import ImprovedOnePassword
from src.utils.config import O365_CREDS_OP_UUID, OP_VAULT_UUID, SERVICE_ACCOUNT_TOKEN_OP_UUID

def setup_env_var_token():
    if not "OP_SERVICE_ACCOUNT_TOKEN" in os.environ.keys():
        op = ImprovedOnePassword()
        item = op.get_item(uuid=SERVICE_ACCOUNT_TOKEN_OP_UUID, fields=['credential'])
        os.environ["OP_SERVICE_ACCOUNT_TOKEN"]=item['credential']
    
def assert_env_var_token_available():
    if not "OP_SERVICE_ACCOUNT_TOKEN" in os.environ.keys():
        logging.error("OP Service Account token not available as env variable")
        raise PermissionError("OP Service Account token not available as env variable")

def get_credentials() -> Tuple[str,str]:
    op = ImprovedOnePassword()
    fields = op.get_item(uuid=O365_CREDS_OP_UUID, vault_uuid=OP_VAULT_UUID, fields=['username', 'credential'])
    return fields['username'], fields['credential']

