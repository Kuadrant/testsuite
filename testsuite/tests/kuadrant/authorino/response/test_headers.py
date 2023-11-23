"""Tests that wrapperKey property returns value in the correct header"""
import json

import pytest

from testsuite.policy.authorization import Value, JsonResponse


@pytest.fixture(scope="module", params=["123456789", "standardCharacters", "specialcharacters+*-."])
def header_name(request):
    """Name of the headers"""
    return request.param


@pytest.fixture(scope="module")
def authorization(authorization, header_name):
    """Add response to Authorization"""
    authorization.responses.clear_all()  # delete previous responses due to the parametrization
    authorization.responses.add_success_header(header_name, JsonResponse({"anything": Value("one")}))
    return authorization


def test_headers(auth, client, header_name):
    """Tests that value in correct Header"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
    data = response.json()["headers"].get(header_name.capitalize(), None)
    assert data is not None, f"Headers from response ({header_name.capitalize()}) is missing"

    extra_data = json.loads(data)
    assert extra_data["anything"] == "one"
