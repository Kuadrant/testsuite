"""Tests that simplest JSON response returns correct header"""

import json

import pytest

from testsuite.policy.authorization import Value, JsonResponse

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add response to Authorization"""
    authorization.responses.add_success_header("header", JsonResponse({"anything": Value("one")}))
    return authorization


def test_simple_response_with(auth, client):
    """Tests simple response"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
    data = response.json()["headers"].get("Header", None)
    assert data is not None, "Header from response (Header) is missing"

    extra_data = json.loads(data)
    assert extra_data["anything"] == "one"
