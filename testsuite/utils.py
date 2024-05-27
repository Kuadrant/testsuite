"""Utility functions for testsuite"""

import csv
import enum
import json
import os
import getpass
import secrets
from collections.abc import Collection
from copy import deepcopy
from dataclasses import is_dataclass, fields
from importlib import resources
from io import StringIO
from typing import Dict, Union
from urllib.parse import urlparse, ParseResult

from weakget import weakget

from testsuite.certificates import Certificate, CFSSLClient, CertInfo
from testsuite.config import settings

MESSAGE_1KB = resources.files("testsuite.resources.performance.files").joinpath("message_1kb.txt")

JSONValues = None | str | int | bool | list["JSONValues"] | dict[str, "JSONValues"]


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
    "To avoid conflicts returns modified name with random suffix"
    return f"{name}-{generate_tail(tail)}"


def _whoami():
    """Returns username"""
    if "tester" in settings:
        return settings["tester"]

    try:
        return getpass.getuser()
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


def extract_response(response, header="Simple", key="data"):
    """
    Extracts response added by Authorino from header
    :param key: Response key section
    :param header: Name of the header
    :param response: http response
    :return: Extracted value
    """

    # Returning None if content is empty, this typically happens for non-200 responses
    if len(response.content) == 0:
        return weakget(None)

    return weakget(json.loads(response.json()["headers"][header]))[key]


def asdict(obj) -> dict[str, JSONValues]:
    """
    This function converts dataclass object to dictionary.
    While it works similar to `dataclasses.asdict` a notable change is usage of
    overriding `asdict()` function if dataclass contains it.
    This function works recursively in lists, tuples and dicts. All other values are passed to copy.deepcopy function.
    """
    if not is_dataclass(obj):
        raise TypeError("asdict() should be called on dataclass instances")
    return _asdict_recurse(obj)


def _asdict_recurse(obj):
    if hasattr(obj, "asdict"):
        return obj.asdict()

    if not is_dataclass(obj):
        return deepcopy(obj)

    result = {}
    for field in fields(obj):
        value = getattr(obj, field.name)
        if value is None:
            continue  # do not include None values

        if is_dataclass(value):
            result[field.name] = _asdict_recurse(value)
        elif isinstance(value, (list, tuple)):
            result[field.name] = type(value)(_asdict_recurse(i) for i in value)
        elif isinstance(value, dict):
            result[field.name] = type(value)((_asdict_recurse(k), _asdict_recurse(v)) for k, v in value.items())
        elif isinstance(value, enum.Enum):
            result[field.name] = value.value
        else:
            result[field.name] = deepcopy(value)
    return result


def check_condition(condition, condition_type, status, reason=None, message=None):
    """Checks if condition matches expectation, won't check message and reason if they are None"""
    if (  # pylint: disable=too-many-boolean-expressions
        condition.type == condition_type
        and condition.status == status
        and (message is None or message in condition.message)
        and (reason is None or reason == condition.reason)
    ):
        return True
    return False


def has_condition(condition_type, status="True", reason=None, message=None):
    """Returns function, that returns True if the Kubernetes object has a specific value"""

    def _check(obj):
        for condition in obj.model.status.conditions:
            if check_condition(condition, condition_type, status, reason, message):
                return True
        return False

    return _check
