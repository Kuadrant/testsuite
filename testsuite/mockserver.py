"""Module for Mockserver integration"""

from typing import Union

from apyproxy import ApyProxy
from httpx import Client

from testsuite.utils import ContentType


class Mockserver:
    """
    Mockserver deployed in Kubernetes (located in Tools or self-managed)
    """

    def __init__(self, client: Client):
        self.url = str(client.base_url)
        self.client = ApyProxy(self.url, session=client)

    def _expectation(self, expectation_id, json_data):
        """
        Creates an Expectation from given expectation json.
        Returns the absolute URL of the expectation
        """
        json_data["id"] = expectation_id
        json_data.setdefault("httpRequest", {})["path"] = f"/{expectation_id}"

        self.client.mockserver.expectation.put(json=json_data)
        # pylint: disable=protected-access
        return f"{self.client._url}/{expectation_id}"

    def create_request_expectation(
        self,
        expectation_id,
        headers: dict[str, list[str]],
    ):
        """Creates an Expectation - request with given headers"""
        json_data = {
            "httpRequest": {
                "headers": headers,
            },
            "httpResponse": {
                "body": "",
            },
        }
        return self._expectation(expectation_id, json_data)

    def create_response_expectation(
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

    def retrieve_requests(self, expectation_id):
        """Verify a request has been received a specific number of times"""
        return self.client.mockserver.retrieve.put(
            params={"type": "REQUESTS", "format": "JSON"},
            json={"path": "/" + expectation_id},
        ).json()
