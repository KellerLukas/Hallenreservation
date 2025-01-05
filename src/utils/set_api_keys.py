import os
from src.utils.config import (
    O365_CLIENT_ID_ENV_VAR,
    O365_SECRET_ENV_VAR,
    OPEN_AI_API_KEY_ENV_VAR,
)


def set_api_key(env_var: str):
    if os.getenv(env_var) is None:
        key = input(f"Enter Api Key for {env_var}: ")
        os.environ[env_var] = key


for key in [OPEN_AI_API_KEY_ENV_VAR, O365_CLIENT_ID_ENV_VAR, O365_SECRET_ENV_VAR]:
    set_api_key(key)
