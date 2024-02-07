"""Tests response configured with AuthJson path"""

import json

import pytest

from testsuite.policy.authorization import ValueFrom, JsonResponse

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def issuer(oidc_provider):
    """Issuer URL"""
    return oidc_provider.well_known["issuer"]


@pytest.fixture(scope="module")
def non_existing():
    """Value, which should returned if the authJSON value doesn't exist"""
    return None


@pytest.fixture(scope="module", params=[("auth.identity.iss", "issuer"), ("auth.non_existing.value", "non_existing")])
def path_and_value(request):
    """Returns authJSON path and expected value"""
    return request.param[0], request.getfixturevalue(request.param[1])


@pytest.fixture(scope="module")
def authorization(authorization, path_and_value):
    """Add response to Authorization"""
    path, _ = path_and_value

    authorization.responses.clear_all()  # delete previous responses due to the parametrization
    authorization.responses.add_success_header("header", JsonResponse({"anything": ValueFrom(path)}))
    return authorization


def test_auth_json_path(auth, client, path_and_value):
    """Tests that path is correctly translated"""
    _, value = path_and_value
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
    data = response.json()["headers"].get("Header", None)
    assert data is not None, "Header from response (Header) is missing"

    extra_data = json.loads(data)
    assert extra_data["anything"] == value
