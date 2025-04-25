"""Common classes for Httpx"""

import typing

# I change return type of HTTPX client to Kuadrant Result
# mypy: disable-error-code="override, return-value"
from tempfile import NamedTemporaryFile
from typing import Union, Iterable

import backoff
from httpx import Client, RequestError, USE_CLIENT_DEFAULT, Request
from httpx._client import UseClientDefault
from httpx._types import (
    URLTypes,
    RequestContent,
    RequestData,
    RequestFiles,
    QueryParamTypes,
    HeaderTypes,
    CookieTypes,
    TimeoutTypes,
    RequestExtensions,
)

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
        return (
            self.has_dns_error()
            or (self.error is None and self.status_code in self.retry_codes)
            or self.has_error("Server disconnected without sending a response.")
            or self.has_error("timed out")
            or self.has_error("SSL: UNEXPECTED_EOF_WHILE_READING")
        )

    def has_error(self, error_msg: str) -> bool:
        """True, if the request failed and an error with message was returned"""
        return self.error is not None and len(self.error.args) > 0 and any(error_msg in arg for arg in self.error.args)

    def has_dns_error(self):
        """True, if the result failed due to DNS failure"""
        return (
            self.has_error("nodename nor servname provided, or not known")
            or self.has_error("Name or service not known")
            or self.has_error("No address associated with hostname")
        )

    def has_tls_error(self):
        """True, if the result failed due to TLS failure"""
        return self.has_error("SSL: UNEXPECTED_EOF_WHILE_READING") or self.has_error("Connection refused")

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
        raise self.error

    def __str__(self):
        if self.error is None:
            return f"Result[status_code={self.response.status_code}]"
        return f"Result[error={self.error}]"


class ResultList(list):
    """List-like object for Result"""

    def assert_all(self, status_code):
        """Assert all responses that contain certain status code"""
        for request in self:
            assert request.status_code == status_code, (
                f"Status code assertion failed for request {self.index(request)+1} out of {len(self)} requests: "
                f"{request} != {status_code}"
            )


class KuadrantClient(Client):
    """Httpx client which retries unstable requests"""

    def __init__(
        self,
        *,
        verify: Union[Certificate, bool] = True,
        cert: Certificate = None,
        retry_codes: Iterable[int] = None,
        **kwargs,
    ):
        self.files = []
        self.retry_codes = retry_codes or {503}
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
        self.verify = _verify or verify
        super().__init__(verify=self.verify, cert=_cert or cert, **kwargs)  # type: ignore

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

    def get_many(self, url, count, *, params=None, headers=None, auth=None) -> ResultList:
        """Send multiple `GET` requests."""
        responses = ResultList()
        for _ in range(count):
            responses.append(self.get(url, params=params, headers=headers, auth=auth))

        return responses


class ForceSNIClient(KuadrantClient):
    """Kuadrant client that forces SNI for each request"""

    def __init__(
        self,
        *,
        verify: Union[Certificate, bool] = True,
        cert: Certificate = None,
        retry_codes: Iterable[int] = None,
        sni_hostname: str = None,
        **kwargs,
    ):
        super().__init__(verify=verify, cert=cert, retry_codes=retry_codes, **kwargs)
        self.sni_hostname = sni_hostname

    def build_request(
        self,
        method: str,
        url: URLTypes,
        *,
        content: RequestContent | None = None,
        data: RequestData | None = None,
        files: RequestFiles | None = None,
        json: typing.Any | None = None,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        cookies: CookieTypes | None = None,
        timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
        extensions: RequestExtensions | None = None,
    ) -> Request:
        extensions = extensions or {}
        extensions.setdefault("sni_hostname", self.sni_hostname)
        return super().build_request(
            method,
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            extensions=extensions,
        )
