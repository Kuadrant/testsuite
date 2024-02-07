"""
Test for checking if multi-element JSON gets parsed correctly.
https://github.com/Kuadrant/authorino/pull/376
"""

import pytest

from testsuite.utils import ContentType, extract_response

pytestmark = [pytest.mark.authorino]

MULTI_ELEMENT_JSON = '{"foo": "bar"}\n{"blah": "bleh"}'


@pytest.fixture(scope="module")
def json_mock_expectation(request, mockserver, module_label):
    """Creates Mockserver Expectation which returns multi-element JSON."""
    request.addfinalizer(lambda: mockserver.clear_expectation(module_label))
    return mockserver.create_expectation(module_label, MULTI_ELEMENT_JSON, ContentType.APPLICATION_JSON)


@pytest.fixture(scope="module")
def authorization(authorization, json_mock_expectation):
    """
    Adds auth metadata HTTP endpoint and header 'Auth-Json' inspecting parsed metadata value.
    """
    authorization.metadata.add_http("mock", json_mock_expectation, "GET")
    authorization.responses.add_simple("auth.metadata.mock")
    return authorization


def test_metadata_contents(client, auth):
    """This test exports parsed metadata value from headers and checks if it is a list of size two."""
    response = client.get("/get", auth=auth)
    extracted = extract_response(response) % None
    assert isinstance(extracted, list)
    assert len(extracted) == 2
