"""Module for Mockserver integration"""
from typing import Union
from urllib.parse import urljoin

import httpx

from testsuite.utils import ContentType


class Mockserver:
    """
    Mockserver deployed in Openshift (located in Tools or self-managed)
    All existing expectations are stored in `self.expectations: dict[expectation_id, expectation_path]`
    """

    def __init__(self, url):
        self.url = url
        self.expectations = {}

    def _expectation(self, expectation_id, response_data):
        """
        Creates an Expectation with given response_data.
        Expectation is accessible on the `mockserver.url/expectation_id` url.
        """
        json_data = {"id": expectation_id, "httpRequest": {"path": f"/{expectation_id}"}}
        json_data.update(response_data)

        response = httpx.put(urljoin(self.url, "/mockserver/expectation"), verify=False, timeout=5, json=json_data)
        response.raise_for_status()
        self.expectations[expectation_id] = f"{self.url}/{expectation_id}"
        return self.expectations[expectation_id]

    def create_expectation(
        self,
        expectation_id,
        body,
        content_type: Union[ContentType, str] = ContentType.PLAIN_TEXT,
    ):
        """Creates an Expectation - response with given body"""
        json_data = {"httpResponse": {"headers": {"Content-Type": [str(content_type)]}, "body": body}}
        return self._expectation(expectation_id, json_data)

    def create_template_expectation(self, expectation_id, template):
        """
        Creates template expectation in Mustache format.
        https://www.mock-server.com/mock_server/response_templates.html
        """
        json_data = {"httpResponseTemplate": {"templateType": "MUSTACHE", "template": template}}
        return self._expectation(expectation_id, json_data)

    def clear_expectation(self, expectation_id):
        """Clears Expectation with specific ID"""
        httpx.put(
            urljoin(self.url, "/mockserver/clear"), verify=False, timeout=5, json={"id": expectation_id}
        ).raise_for_status()
        del self.expectations[expectation_id]

    def verify_expectation(self, path):
        """Verify a request has been received a specific number of times for specific expectation"""
        return httpx.put(
            urljoin(self.url, "/mockserver/retrieve"),
            params="type=REQUESTS&format=JSON",
            verify=False,
            timeout=5,
            json={"path": path},
        )

    def get_expectation_endpoint(self, expectation_id):
        """Returns endpoint for expectation"""
        return f"{self.url}/{expectation_id}"
