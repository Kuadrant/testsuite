"""Common classes for Httpx"""
from tempfile import NamedTemporaryFile
from typing import Union

import backoff
from httpx import Client, Response

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
    """Slightly different response attributes were expected"""
    def __init__(self, msg, response):
        super().__init__(msg)
        self.response = response


class HttpxBackoffClient(Client):
    """Httpx client which retries unstable requests"""
    RETRY_CODES = {503}

    def __init__(self, *, verify: Union[Certificate, bool] = True, cert: Certificate = None, **kwargs):
        self.files = []
        _verify = None
        if isinstance(verify, Certificate):
            verify_file = create_tmp_file(verify.certificate)
            self.files.append(verify_file)
            _verify = verify_file.name
        _cert = None
        if cert:
            cert_file = create_tmp_file(cert.certificate)
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
