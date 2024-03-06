"""Auth Classes for HttpX"""

from functools import cached_property
from typing import Generator, Callable, Union

from httpx import Auth, Request, URL, Response

from testsuite.oidc.rhsso import User
from testsuite.oidc import Token

TokenType = Union[Token, Callable[[], Token]]


class HttpxOidcClientAuth(Auth):
    """Auth class for Httpx client for product secured by oidc"""

    def __init__(self, token: TokenType, location="authorization", username: str = None, password: str = None) -> None:
        self.location = location
        self._token = token
        self.username = username
        self.password = password

    @classmethod
    def from_user(cls, token: TokenType, user: User, location="authorization"):
        """Creates Auth from RHSSO User object"""
        return cls(token, location, user.username, user.password)

    @cached_property
    def token(self):
        """Lazily retrieves token from OIDC provider"""
        if callable(self._token):
            return self._token(self.username, self.password)
        return self._token

    def _add_credentials(self, request: Request, token):
        if self.location == "authorization":
            request.headers["Authorization"] = f"Bearer {token}"
        elif self.location == "headers":
            request.headers["access_token"] = token
        elif self.location == "query":
            request.url = URL(request.url, params={"access_token": token})
        else:
            raise ValueError(f"Unknown credentials location '{self.location}'")

    def auth_flow(self, request: Request) -> Generator[Request, Response, None]:
        self._add_credentials(request, self.token.access_token)
        response = yield request

        if response.status_code == 403:
            # Renew access token and try again
            self.token.refresh()
            self._add_credentials(request, self.token.access_token)
            yield request


class HeaderApiKeyAuth(Auth):
    """Auth class for authentication with API key"""

    def __init__(self, api_key, prefix: str = "APIKEY") -> None:
        super().__init__()
        self.api_key = str(api_key)
        self.prefix = prefix

    def auth_flow(self, request: Request) -> Generator[Request, Response, None]:
        request.headers["Authorization"] = f"{self.prefix} {self.api_key}"
        yield request
