# mypy: ignore-errors
from O365 import Account
from typing import Optional


class FixedAccount(Account):
    def get_consent_url(
        self, *, requested_scopes: Optional[list] = None, redirect_uri, **kwargs
    ) -> tuple[str, dict]:
        """In VS Code the input of the token_url seems to be buggy or not work at all.
        This divides the authentication method into two steps as a workaround.
        """

        if self.con.auth_flow_type in ("authorization", "public"):
            consent_url, flow = self.get_authorization_url(
                requested_scopes, redirect_uri=redirect_uri, **kwargs
            )
            return consent_url, flow

        elif self.con.auth_flow_type in ("credentials", "certificate", "password"):
            return self.con.request_token(
                None, requested_scopes=requested_scopes, **kwargs
            )
        else:
            raise ValueError(
                'Connection "auth_flow_type" must be "authorization", "public", "password", "certificate"'
                ' or "credentials"'
            )

    def put_token_url(self, token_url: str, flow, **kwargs) -> bool:
        if token_url:
            result = self.request_token(
                token_url, flow=flow, **kwargs
            )  # no need to pass state as the session is the same
            if result:
                print(
                    "Authentication Flow Completed. Oauth Access Token Stored. You can now use the API."
                )
            else:
                print("Something go wrong. Please try again.")

            return bool(result)
        else:
            print("No token_url provided")
            return False
