"""Common classes for Httpx"""
# I change return type of HTTPX client to Kuadrant Result
# mypy: disable-error-code="override, return-value"
from tempfile import NamedTemporaryFile
from typing import Union

import backoff
from httpx import Client, RequestError

from testsuite.certificates import Certificate


def create_tmp_file(content: str):
    """Creates temporary file and writes content into it"""
    # I need them open until the client closes
    # pylint: disable=consider-using-with
    file = NamedTemporaryFile()
    file.write(content.encode("utf-8"))
    file.flush()
    return file


class Result:
    """Result from HTTP request"""

    def __init__(self, retry_codes, response=None, error=None):
        self.response = response
        self.error = error
        self.retry_codes = retry_codes

    def should_backoff(self):
        """True, if the Result can be considered an instability and should be retried"""
        return self.has_dns_error() or (self.error is None and self.status_code in self.retry_codes)

    def has_error(self, error_msg: str) -> bool:
        """True, if the request failed and an error with message was returned"""
        return self.error is not None and len(self.error.args) > 0 and any(error_msg in arg for arg in self.error.args)

    def has_dns_error(self):
        """True, if the result failed due to DNS failure"""
        return self.has_error("Name or service not known")

    def has_cert_verify_error(self):
        """True, if the result failed due to TLS certificate verification failure"""
        return self.has_error("SSL: CERTIFICATE_VERIFY_FAILED")

    def has_unknown_ca_error(self):
        """True, if the result failed due to TLS unknown certificate authority failure"""
        return self.has_error("SSL: TLSV1_ALERT_UNKNOWN_CA")

    def has_cert_required_error(self):
        """True, if the result failed due to TLS certificate absense failure"""
        return self.has_error("SSL: TLSV13_ALERT_CERTIFICATE_REQUIRED")

    def __getattr__(self, item):
        """For backwards compatibility"""
        if self.response is not None:
            return getattr(self.response, item)
        return None


class KuadrantClient(Client):
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
    @backoff.on_predicate(backoff.fibo, lambda result: result.should_backoff(), max_tries=8, jitter=None)
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
    ) -> Result:
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
            return Result(self.retry_codes, response=response)
        except RequestError as e:
            return Result(self.retry_codes, error=e)

    def get(self, *args, **kwargs) -> Result:
        return super().get(*args, **kwargs)

    def get_many(self, url, count, *, params=None, headers=None, auth=None) -> list[Result]:
        """Send multiple `GET` requests."""
        responses = []
        for _ in range(count):
            responses.append(self.get(url, params=params, headers=headers, auth=auth))

        return responses
