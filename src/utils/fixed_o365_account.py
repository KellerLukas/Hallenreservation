from O365 import Account
from typing import Optional

class FixedAccount(Account):
    def get_consent_url(self, *, scopes: Optional[list] = None, **kwargs) -> str:
        """ In VS Code the input of the token_url seems to be buggy or not work at all.
        This divides the authentication method into two steps as a workaround.
        """

        if self.con.auth_flow_type in ('authorization', 'public'):
            if scopes is not None:
                if self.con.scopes is not None:
                    raise RuntimeError('The scopes must be set either at the Account '
                                       'instantiation or on the account.authenticate method.')
                self.con.scopes = self.protocol.get_scopes_for(scopes)
            else:
                if self.con.scopes is None:
                    raise ValueError('The scopes are not set. Define the scopes requested.')

            consent_url, _ = self.con.get_authorization_url(**kwargs)
            return consent_url
        
        elif self.con.auth_flow_type in ('credentials', 'certificate', 'password'):
            return self.con.request_token(None, requested_scopes=scopes, **kwargs)
        else:
            raise ValueError('Connection "auth_flow_type" must be "authorization", "public", "password", "certificate"'
                             ' or "credentials"')
            
    def put_token_url(self, token_url: str, **kwargs) -> bool:
        if token_url:
            result = self.con.request_token(token_url, **kwargs)  # no need to pass state as the session is the same
            if result:
                print('Authentication Flow Completed. Oauth Access Token Stored. You can now use the API.')
            else:
                print('Something go wrong. Please try again.')

            return bool(result)
        else:
            print("No token_url provided")
            return False