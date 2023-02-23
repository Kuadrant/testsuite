"""Module containing all classes necessary to work with Auth0"""
from functools import cached_property

import httpx

from testsuite.oidc import OIDCProvider, Token


class Auth0Provider(OIDCProvider):
    """Auth0 OIDC provider"""

    def __init__(self, domain, client_id, client_secret) -> None:
        super().__init__()
        self.domain = domain
        self.client_id = client_id
        self.client_secret = client_secret

    @property
    def token_endpoint(self):
        """Returns token_endpoint URL"""
        return self.well_known["token_endpoint"]

    @cached_property
    def well_known(self):
        response = httpx.get(self.domain + "/.well-known/openid-configuration")
        return response.json()

    # pylint: disable=unused-argument
    def refresh_token(self, refresh_token):
        """Refresh tokens are not yet implemented for Auth0, will attempt to acquire new token instead"""
        return self.get_token()

    def get_token(self, username=None, password=None) -> Token:
        response = httpx.post(
            self.token_endpoint,
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
                "audience": self.domain + "/api/v2/",
            },
        )
        data = response.json()
        assert response.status_code == 200, f"Unable to acquire token from Auth0, reason: {data}"
        return Token(data["access_token"], self.refresh_token, "None")
