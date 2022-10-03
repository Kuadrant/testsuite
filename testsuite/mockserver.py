"""Module for Mockserver integration"""
from typing import Union
from urllib.parse import urljoin

import httpx

from testsuite.utils import ContentType


class Mockserver:
    """Mockserver deployed in Openshift (located in Tools or self-managed)"""

    def __init__(self, url):
        self.url = url

    def create_expectation(self, expectation_id, path, opa_policy,
                           content_type: Union[ContentType, str] = ContentType.PLAIN_TEXT):
        """Creates an Expectation - response with body that contains OPA policy (Rego query)"""
        response = httpx.put(
            urljoin(self.url, "/mockserver/expectation"), verify=False, timeout=5, json={
                    "id": expectation_id,
                    "httpRequest": {
                        "path": path
                    },
                    "httpResponse": {
                        "headers": {
                            "Content-Type": [str(content_type)]
                        },
                        "body": opa_policy
                    }
                }
            )
        response.raise_for_status()
        return self.url + path

    def clear_expectation(self, expectation_id):
        """Clears Expectation with specific ID"""
        httpx.put(
            urljoin(self.url, "/mockserver/clear"), verify=False, timeout=5, json={
                    "id": expectation_id
                }
            ).raise_for_status()
