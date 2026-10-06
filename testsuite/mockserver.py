"""Module for Mockserver integration"""

import json
from typing import Union, Literal

from apyproxy import ApyProxy
from httpx import Client
from mockserver.llm import Completion, HttpLlmResponse
from mockserver.models import Body, Expectation, HttpRequest, HttpResponse

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
    ):
        """
        Creates an Expectation returning a provider-shaped LLM response body (OpenAI, Anthropic,
        Gemini, ...) via MockServer's LLM response mocking. Unlike the other
        `create_*_expectation` helpers, `path` is used as given rather than derived from
        `expectation_id`, since the generated shape depends on `provider`/`path` matching that
        provider's real API route. See `mockserver.llm` for `completion` construction.
        https://www.mock-server.com/mock_server/llm_response_mocking.html

        `Provider.BEDROCK` does NOT produce a real AWS Bedrock Converse API shape despite the docs
        above: it emits the older Anthropic-on-Bedrock InvokeModel shape instead (snake_case
        usage.input_tokens/output_tokens, no total). Use create_json_expectation with a hand-crafted
        body for Bedrock Converse instead.
        """
        expectation = Expectation(
            id=expectation_id,
            http_request=HttpRequest(method=method, path=path),
            http_llm_response=HttpLlmResponse(provider=provider, model=model, completion=completion),
        )
        self.client.mockserver.expectation.put(json=expectation.to_dict())
        return path

    def create_json_expectation(self, expectation_id, path: str, body: dict, method: str = "POST"):
        """
        Creates an Expectation returning a literal JSON response body at the given path. Unlike
        `create_response_expectation`, `path` is used as given rather than derived from
        `expectation_id` - useful for hand-crafting a provider's real wire shape when MockServer's
        own LLM response mocking doesn't (yet) model that shape correctly. The body is serialized
        compact (no indentation): passing `body` as a plain dict makes MockServer pretty-print it
        when serving, and Kuadrant's wasm data plane fails to extract JSON Pointer values (e.g.
        dataExtraction.response.totalTokens) from an indented body - a wasm-shim bug tracked
        upstream in acutejson: https://github.com/alexsnaps/acutejson/pull/1.

        TODO: once that fix ships in a Kuadrant/RHCL release this test suite picks up, drop the
        compact-serialization workaround below and pass `body` straight through again.
        """
        compact_body = Body(
            type="STRING", string=json.dumps(body, separators=(",", ":")), content_type="application/json"
        )
        expectation = Expectation(
            id=expectation_id,
            http_request=HttpRequest(method=method, path=path),
            http_response=HttpResponse(status_code=200, body=compact_body),
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
