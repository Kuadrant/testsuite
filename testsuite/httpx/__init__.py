"""Common classes for Httpx"""
from tempfile import NamedTemporaryFile
from typing import Union

import backoff
from httpx import Client, Response, ConnectError

from testsuite.certificates import Certificate


def create_tmp_file(content: str):
    """Creates temporary file and writes content into it"""
    # I need them open until the client closes
    # pylint: disable=consider-using-with
    file = NamedTemporaryFile()
    file.write(content.encode("utf-8"))
    file.flush()
    return file


class UnexpectedResponse(Exception):
    """Slightly different response attributes were expected or no response was given"""

    def __init__(self, msg, response):
        super().__init__(msg)
        self.response = response


class HttpxBackoffClient(Client):
    """Httpx client which retries unstable requests"""

    def __init__(self, *, verify: Union[Certificate, bool] = True, cert: Certificate = None, **kwargs):
        self.files = []
        self.retry_codes = {503}
        _verify = None
        if isinstance(verify, Certificate):
            verify_file = create_tmp_file(verify.chain)
            self.files.append(verify_file)
            _verify = verify_file.name
        _cert = None
        if cert:
            cert_file = create_tmp_file(cert.chain)
            self.files.append(cert_file)
            key_file = create_tmp_file(cert.key)
            self.files.append(key_file)
            _cert = (cert_file.name, key_file.name)

        # Mypy does not understand the typing magic I have done
        super().__init__(verify=_verify or verify, cert=_cert or cert, **kwargs)  # type: ignore

    def close(self) -> None:
        super().close()
        for file in self.files:
            file.close()
        self.files = []

    def add_retry_code(self, code):
        """Add a new retry code to"""
        self.retry_codes.add(code)

    # pylint: disable=too-many-locals
    @backoff.on_exception(backoff.fibo, UnexpectedResponse, max_tries=8, jitter=None)
    def request(
        self,
        method: str,
        url,
        *,
        content=None,
        data=None,
        files=None,
        json=None,
        params=None,
        headers=None,
        cookies=None,
        auth=None,
        follow_redirects=None,
        timeout=None,
        extensions=None,
    ) -> Response:
        try:
            response = super().request(
                method,
                url,
                content=content,
                data=data,
                files=files,
                json=json,
                params=params,
                headers=headers,
                cookies=cookies,
                auth=auth,
                follow_redirects=follow_redirects,
                timeout=timeout,
                extensions=extensions,
            )
            if response.status_code in self.retry_codes:
                raise UnexpectedResponse(f"Didn't expect '{response.status_code}' status code", response)
            return response
        except ConnectError as e:
            # note: when the code reaches this point, negative caching might have been triggered,
            # negative caching TTL of SOA record of the zone must be set accordingly,
            # otherwise retry will fail if the value is too high
            if len(e.args) > 0 and any("Name or service not known" in arg for arg in e.args):
                raise UnexpectedResponse("Didn't expect 'Name or service not known' error", None) from e
            raise

    def get_many(self, url, count, *, params=None, headers=None, auth=None) -> list[Response]:
        """Send multiple `GET` requests."""
        responses = []
        for _ in range(count):
            responses.append(self.get(url, params=params, headers=headers, auth=auth))

        return responses
