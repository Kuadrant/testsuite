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
            raise ValueError("Unknown credentials location '%s'" % self.location)

    def auth_flow(self, request: Request) -> Generator[Request, Response, None]:
        self._add_credentials(request, self.token["access_token"])
        response = yield request

        if response.status_code == 403:
            # Renew access token and try again
            self.token = self.oidc_client.refresh_token(self.token["refresh_token"])
            self._add_credentials(request, self.token["access_token"])
            yield request
