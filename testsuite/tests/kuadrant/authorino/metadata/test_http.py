"""
Tests for external auth metadata fetched from HTTP endpoint:
https://github.com/Kuadrant/authorino/blob/main/docs/features.md#http-getget-by-post-metadatahttp
Test setup consist of:
    1. External metadata located on HTTP endpoint: Create Mockserver expectation that returns
       JSON with one key-value pair - `ALLOWED_COUNTRY`.
    2. Add OPA policy to AuthConfig. Rego query (`CHECK_COUNTRY_REGO`) parses the request path and allows only those
       containing country code saved in metadata.
"""

import pytest

from testsuite.utils import ContentType

pytestmark = [pytest.mark.authorino]


ALLOWED_COUNTRY = {"countryCode": "SK"}
CHECK_COUNTRY_REGO = """allow {
split(input.context.request.http.path, "/") = [_, _, country_code]
country_code == object.get(input.auth.metadata.mock, "countryCode", "")}
"""


@pytest.fixture(scope="module")
def country_mock_expectation(request, mockserver, module_label):
    """Creates Mockserver Expectation which returns simple JSON that contains `allowed_countries`"""
    request.addfinalizer(lambda: mockserver.clear_expectation(module_label))
    return mockserver.create_expectation(module_label, ALLOWED_COUNTRY, ContentType.APPLICATION_JSON)


@pytest.fixture(scope="module")
def authorization(authorization, country_mock_expectation, module_label):
    """
    Adds auth metadata HTTP endpoint and simple OPA policy that accepts requests,
    which contain a specific country code in their path - `/anything/{country_code}
    """
    authorization.metadata.add_http("mock", country_mock_expectation, "GET")
    authorization.authorization.add_opa_policy("opa_" + module_label, CHECK_COUNTRY_REGO)
    return authorization


def test_authorized(client, auth):
    """Test correct auth when valid country code (SK) is returned by mocked HTTP metadata"""
    response = client.get("/anything/SK", auth=auth)
    assert response.status_code == 200


def test_decline_authorization(client, auth):
    """Test incorrect auth when invalid country code (CZ) is returned by mocked HTTP metadata"""
    response = client.get("/anything/CZ", auth=auth)
    assert response.status_code == 403
