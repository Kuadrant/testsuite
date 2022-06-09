"""Common classes for Httpx"""
import backoff
from httpx import Client, Response


class UnexpectedResponse(Exception):
    """Slightly different response attributes were expected"""
    def __init__(self, msg, response):
        super().__init__(msg)
        self.response = response


class HttpxBackoffClient(Client):
    """Httpx client which retries unstable requests"""
    RETRY_CODES = {503}

    @backoff.on_exception(backoff.fibo, UnexpectedResponse, max_tries=8, jitter=None)
    def request(self, method: str, url, *, content=None, data=None, files=None,
                json=None, params=None, headers=None, cookies=None, auth=None, follow_redirects=None,
                timeout=None, extensions=None) -> Response:
        response = super().request(method, url, content=content, data=data, files=files, json=json, params=params,
                                   headers=headers, cookies=cookies, auth=auth, follow_redirects=follow_redirects,
                                   timeout=timeout, extensions=extensions)
        if response.status_code in self.RETRY_CODES:
            raise UnexpectedResponse(f"Didn't expect '{response.status_code}' status code", response)
        return response
