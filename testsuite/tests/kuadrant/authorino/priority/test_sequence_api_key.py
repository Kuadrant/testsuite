"""Test for api key identities, with different credential methods, sequential trigger according to their priorities"""
import pytest

from testsuite.objects import Credentials
from testsuite.utils import extract_response


@pytest.fixture(scope="module")
def first_label(blame):
    """Label for the first API key match"""
    return blame("first-label")


@pytest.fixture(scope="module")
def second_label(blame):
    """Label for the second API key match"""
    return blame("second-label")


@pytest.fixture(scope="module")
def first_api_key(create_api_key, first_label):
    """Create first API key"""
    return create_api_key("api-key-first", first_label, "first-key")


@pytest.fixture(scope="module")
def second_api_key(create_api_key, second_label):
    """Create second API key"""
    return create_api_key("api-key-second", second_label, "second-key")


@pytest.fixture(scope="module")
def authorization(authorization, first_api_key, second_api_key):
    """Add 2 API key identities with different credential method and priority to the AuthConfig"""
    authorization.identity.add_api_key(
        "priority-zero",
        selector=first_api_key.selector,
        credentials=Credentials("authorization_header", "APIKEY"),
        priority=0,
    )
    authorization.identity.add_api_key(
        "priority-one", selector=second_api_key.selector, credentials=Credentials("query", "APIKEY"), priority=1
    )

    return authorization


def test_priority_api_key(client, first_api_key, second_api_key, first_label, second_label):
    """Send request with both credential methods at once and verify if high priority key was used."""
    # verify that first API key is available to identify with and is used for identification
    response = client.get("/get", headers={"authorization": "APIKEY " + first_api_key.value})
    assert response.status_code == 200
    label = extract_response(response)["identity"]["metadata"]["labels"]["group"] % None
    assert label == first_label

    # verify that second API key is available to identify with and is used for identification
    response = client.get("/get", params={"APIKEY": second_api_key.value})
    assert response.status_code == 200
    label = extract_response(response)["identity"]["metadata"]["labels"]["group"] % None
    assert label == second_label

    # verify that if both keys credential methods are used at the same time,
    # the API key with the highest priority will be used for identification
    response = client.get(
        "/get", headers={"authorization": "APIKEY " + first_api_key.value}, params={"APIKEY": second_api_key.value}
    )
    assert response.status_code == 200
    label = extract_response(response)["identity"]["metadata"]["labels"]["group"] % None
    assert label == first_label
