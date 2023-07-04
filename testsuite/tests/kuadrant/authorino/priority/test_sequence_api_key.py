"""Test for api key identities, with different credential methods, sequential trigger according to their priorities"""
import pytest

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
    first_key = "first-key"
    create_api_key("api-key-first", first_label, first_key)
    return first_key


@pytest.fixture(scope="module")
def second_api_key(create_api_key, second_label):
    """Create second API key"""
    second_key = "second-key"
    create_api_key("api-key-second", second_label, second_key)
    return second_key


@pytest.fixture(scope="module")
def authorization(authorization, first_label, second_label):
    """Add 2 API key identities with different credential method and priority to the AuthConfig"""
    authorization.identity.api_key(
        "priority-zero", match_label=first_label, credentials="authorization_header", priority=0
    )
    authorization.identity.api_key("priority-one", match_label=second_label, credentials="query", priority=1)

    return authorization


def test_priority_api_key(client, first_api_key, second_api_key, first_label, second_label):
    """Send request with both credential methods at once and verify if high priority key was used."""
    # verify that first API key is available to identify with and is used for identification
    response = client.get("/get", headers={"authorization": "APIKEY " + first_api_key})
    assert response.status_code == 200
    label = extract_response(response)["identity"]["metadata"]["labels"]["group"] % None
    assert label == first_label

    # verify that second API key is available to identify with and is used for identification
    response = client.get("/get", params={"APIKEY": second_api_key})
    assert response.status_code == 200
    label = extract_response(response)["identity"]["metadata"]["labels"]["group"] % None
    assert label == second_label

    # verify that if both keys credential methods are used at the same time,
    # the API key with the highest priority will be used for identification
    response = client.get(
        "/get", headers={"authorization": "APIKEY " + first_api_key}, params={"APIKEY": second_api_key}
    )
    assert response.status_code == 200
    label = extract_response(response)["identity"]["metadata"]["labels"]["group"] % None
    assert label == first_label
