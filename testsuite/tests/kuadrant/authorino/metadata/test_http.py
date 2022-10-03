"""Tests for external auth metadata fetched from HTTP endpoint"""
import pytest


ALLOWED_COUNTRY = {"countryCode": "SK"}
REGO = """allow {
split(input.context.request.http.path, "/") = [_, _, country_code]
lower(country_code) == lower(object.get(input.auth.metadata.mock, "countryCode", ""))}
"""


@pytest.fixture(scope="module")
def country_mock_expectation(request, mockserver, module_label):
    """Creates Mockserver Expectation which returns simple JSON that contains `allowed_countries`"""
    request.addfinalizer(lambda: mockserver.clear_expectation(module_label))
    return mockserver.create_expectation(module_label, f"/{module_label}/opa", ALLOWED_COUNTRY)


@pytest.fixture(scope="module")
def authorization(authorization, country_mock_expectation, module_label):
    """
    Adds auth metadata HTTP endpoint and simple OPA policy that accepts requests,
    which contain a specific country code in their path - `/anything/{coutry_code}
    """
    authorization.add_metadata_http("metadata_" + module_label, country_mock_expectation, "GET")
    authorization.add_opa_policy("opa_" + module_label, REGO)
    return authorization


def test_authorized(client, auth):
    """Test correct auth when valid country code (SK) is returned by mocked HTTP metadata"""
    response = client.get("/anything/SK", auth=auth)
    assert response.status_code == 200


def test_decline_authorization(client, auth):
    """Test incorrect auth when invalid country code (CZ) is returned by mocked HTTP metadata"""
    response = client.get("/anything/CZ", auth=auth)
    assert response.status_code == 403
