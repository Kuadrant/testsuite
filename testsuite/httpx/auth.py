"""Auth Classes for HttpX"""
import typing
from typing import Generator

from httpx import Auth, Request, URL, Response

from testsuite.rhsso import Client


class HttpxOidcClientAuth(Auth):
    """Auth class for Httpx client for product secured by oidc"""

    def __init__(self, client: Client, location, username=None, password=None) -> None:
        self.location = location
        self.oidc_client = client.oidc_client
        self.token = self.oidc_client.token(username, password)

    def _add_credentials(self, request: Request, token):
        if self.location == 'authorization':
            request.headers['Authorization'] = f"Bearer {token}"
        elif self.location == 'headers':
            request.headers['access_token'] = token
        elif self.location == 'query':
            request.url = URL(request.url, params={'access_token': token})
        else:
            raise ValueError(f"Unknown credentials location '{self.location}'")

    def auth_flow(self, request: Request) -> Generator[Request, Response, None]:
        self._add_credentials(request, self.token["access_token"])
        response = yield request

        if response.status_code == 403:
            # Renew access token and try again
            self.token = self.oidc_client.refresh_token(self.token["refresh_token"])
            self._add_credentials(request, self.token["access_token"])
            yield request


class HeaderApiKeyAuth(Auth):
    """Auth class for authentication with API key"""

    def __init__(self, api_key: str, prefix: str = "APIKEY") -> None:
        super().__init__()
        self.api_key = api_key
        self.prefix = prefix

    def auth_flow(self, request: Request) -> typing.Generator[Request, Response, None]:
        request.headers["Authorization"] = f"{self.prefix} {self.api_key}"
        yield request
