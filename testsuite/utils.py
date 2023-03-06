"""Utility functions for testsuite"""
import csv
import enum
import os
import secrets
from collections.abc import Collection
from importlib import resources
from io import StringIO
from typing import Dict, Union
from urllib.parse import urlparse, ParseResult

from testsuite.certificates import Certificate, CFSSLClient, CertInfo
from testsuite.config import settings

MESSAGE_1KB = resources.files("testsuite.resources.performance.files").joinpath("message_1kb.txt")


class ContentType(enum.Enum):
    """Content-type options for expectation headers"""

    PLAIN_TEXT = "plain/text"
    APPLICATION_JSON = "application/json"

    def __str__(self):
        return str(self.value)


def generate_tail(tail=5):
    """Returns random suffix"""
    return secrets.token_urlsafe(tail).translate(str.maketrans("", "", "-_")).lower()


def randomize(name, tail=5):
    "To avoid conflicts returns modified name with random sufffix"
    return f"{name}-{generate_tail(tail)}"


def _whoami():
    """Returns username"""
    if "tester" in settings:
        return settings["tester"]

    try:
        return os.getlogin()
    # want to catch broad exception and fallback at any circumstance
    # pylint: disable=broad-except
    except Exception:
        return str(os.getuid())


def cert_builder(
    cfssl: CFSSLClient, chain: dict, hosts: Union[str, Collection[str]] = None, parent: Certificate = None
) -> Dict[str, Certificate]:
    """
    Recursively create certificates based on their given CertInfo.
    If CertInfo has children or is marked as CA, it will be generated as a Certificate Authority,
     otherwise it will be a Certificate.
    Example input:
        {"envoy_ca": CertInfo(children={
            "envoy_cert": None,
            "valid_cert": None
            })
        }
    Will generate envoy_ca as a Certificate Authority with two certificate (envoy_cert, valid_cert) signed by it
    """
    result = {}
    for name, info in chain.items():
        if info is None:
            info = CertInfo()

        parsed_hosts: Collection[str] = info.hosts or hosts  # type: ignore
        if isinstance(parsed_hosts, str):
            parsed_hosts = [parsed_hosts]  # type: ignore

        if info.ca or info.children:
            cert = cfssl.create_authority(name, names=info.names, hosts=parsed_hosts, certificate_authority=parent)
        else:
            cert = cfssl.create(name, names=info.names, hosts=parsed_hosts, certificate_authority=parent)

        if info.children is not None:
            result.update(cert_builder(cfssl, info.children, parsed_hosts, cert))
        result[name] = cert
    return result


def rego_allow_header(key, value):
    """Rego query that allows all requests that contain specific header with`key` and `value`"""
    return f'allow {{ input.context.request.http.headers.{key} == "{value}" }}'


def add_port(url_str: str, return_netloc=True) -> Union[ParseResult, str]:
    """Adds port number to url if it is not set"""
    url = urlparse(url_str)
    if not url.hostname:
        raise ValueError("Missing hostname part of url")
    if not url.port:
        url_port = 80 if url.scheme == "http" else 443
        url = url._replace(netloc=url.hostname + f":{url_port}")
    return url.netloc if return_netloc else url


def create_csv_file(rows: list) -> StringIO:
    """Creates in-memory CSV file with specified rows"""
    file = StringIO()
    csv.writer(file, delimiter=",", quotechar='"', quoting=csv.QUOTE_ALL).writerows(rows)
    file.seek(0)
    return file
