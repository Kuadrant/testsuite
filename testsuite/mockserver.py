"""Module for Mockserver integration"""

from typing import Union, Literal

from apyproxy import ApyProxy
from httpx import Client
from mockserver.llm import Completion, HttpLlmResponse
from mockserver.models import Expectation, HttpRequest

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

    def create_template_expectation(
        self, expectation_id, template, template_type: Literal["MUSTACHE", "VELOCITY"] = "MUSTACHE"
    ):
        """
        Creates template expectation in Mustache or Velocity format.
        https://www.mock-server.com/mock_server/response_templates.html
        """
        json_data = {"httpResponseTemplate": {"templateType": template_type, "template": template}}
        return self._expectation(expectation_id, json_data)

    def create_llm_response_expectation(
        self,
        expectation_id,
        path: str,
        provider: str,
        completion: Completion,
        model: str | None = None,
        method: str = "POST",
        query: dict[str, str] | None = None,
    ):
        """
        Creates an Expectation returning a provider-shaped LLM response body (OpenAI, Anthropic,
        Gemini, ...) via MockServer's LLM response mocking. Unlike the other
        `create_*_expectation` helpers, `path` is used as given rather than derived from
        `expectation_id`, since the generated shape depends on `provider`/`path` matching that
        provider's real API route. `query` matches request query string parameters, e.g. Gemini's
        `?alt=sse` toggle for Server-Sent Events. See `mockserver.llm` for `completion` construction.
        https://www.mock-server.com/mock_server/llm_response_mocking.html
        """
        expectation = Expectation(
            id=expectation_id,
            http_request=HttpRequest(method=method, path=path, query_string_parameters=query),
            http_llm_response=HttpLlmResponse(provider=provider, model=model, completion=completion),
        )
        self.client.mockserver.expectation.put(json=expectation.to_dict())
        return path

    def clear_expectation(self, expectation_id):
        """Clears Expectation with specific ID"""
        return self.client.mockserver.clear.put(json={"id": expectation_id})

    def clear_expectations_at_path(self, path: str, method: str = "POST"):
        """
        Clears all expectation(s) matching the given method/path, regardless of id. Needed before
        registering a new expectation on a path that a previous, id-distinct expectation already
        occupies (e.g. a streaming and a non-streaming variant of the same real provider API path) -
        otherwise both would remain registered and which one MockServer matches is unpredictable.
        """
        return self.client.mockserver.clear.put(json={"path": path, "method": method})

    def retrieve_requests(self, expectation_id):
        """Verify a request has been received a specific number of times"""
        return self.client.mockserver.retrieve.put(
            params={"type": "REQUESTS", "format": "JSON"},
            json={"path": "/" + expectation_id},
        ).json()

    def retrieve_requests_by_header(self, header_name, header_value):
        """Retrieve requests matching a specific header value"""
        return self.client.mockserver.retrieve.put(
            params={"type": "REQUESTS", "format": "JSON"},
            json={"headers": {header_name: [header_value]}},
        ).json()
