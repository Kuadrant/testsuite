"""Tests multiple responses specified"""

import json

import pytest

from testsuite.kuadrant.policy.authorization import Value, JsonResponse

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add response to Authorization"""
    authorization.responses.add_success_header("header", JsonResponse({"anything": Value("one")}))
    authorization.responses.add_success_header("X-Test", JsonResponse({"anything": Value("two")}))
    return authorization


def test_multiple_responses(auth, client):
    """Test that both headers are present"""
    response = client.get("/get", auth=auth)

    assert response.status_code == 200
    data = response.json()["headers"].get("header", None)
    assert data is not None, "Headers from first response (header) is missing"

    extra_data = json.loads(data)
    assert extra_data["anything"] == "one"

    data = response.json()["headers"].get("x-test", None)
    assert data is not None, "Headers from second response (x-test) is missing"

    extra_data = json.loads(data)
    assert extra_data["anything"] == "two"
