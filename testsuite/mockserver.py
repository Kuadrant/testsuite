"""Module for Mockserver integration"""
from typing import Union

import httpx
from apyproxy import ApyProxy

from testsuite.utils import ContentType


class Mockserver:
    """
    Mockserver deployed in Openshift (located in Tools or self-managed)
    """

    def __init__(self, url):
        self.client = ApyProxy(url, session=httpx.Client(verify=False, timeout=5))

    def _expectation(self, expectation_id, response_data):
        """
        Creates an Expectation with given response_data.
        Returns the absolute URL of the expectation
        """
        json_data = {"id": expectation_id, "httpRequest": {"path": f"/{expectation_id}"}}
        json_data.update(response_data)

        self.client.mockserver.expectation.put(json=json_data)
        # pylint: disable=protected-access
        return f"{self.client._url}/{expectation_id}"

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
        return self.client.mockserver.clear.put(json={"id": expectation_id})

    def retrieve_requests(self, path):
        """Verify a request has been received a specific number of times"""
        return self.client.mockserver.retrieve.put(
            params={"type": "REQUESTS", "format": "JSON"},
            json={"path": path},
        ).json()
