"""Test for API key auth credentials"""

import pytest

from testsuite.kuadrant.policy.authorization import Credentials

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module", params=["authorizationHeader", "customHeader", "queryString", "cookie"])
def credentials(request):
    """Location where are auth credentials passed"""
    return request.param


@pytest.fixture(scope="module")
def authorization(authorization, api_key, credentials):
    """Add API key identity to AuthConfig"""
    authorization.identity.add_api_key(
        "api_key", credentials=Credentials(credentials, "APIKEY"), selector=api_key.selector
    )
    return authorization


def test_custom_selector(client, auth, credentials):
    """Test if auth credentials are stored in right place"""
    response = client.get("/get", headers={"authorization": "APIKEY " + auth.api_key})
    if credentials == "authorizationHeader":
        assert response.status_code == 200
    else:
        assert response.status_code == 401


def test_custom_header(client, auth, credentials):
    """Test if auth credentials are stored in right place"""
    response = client.get("/get", headers={"APIKEY": auth.api_key})
    if credentials == "customHeader":
        assert response.status_code == 200
    else:
        assert response.status_code == 401


def test_query(client, auth, credentials):
    """Test if auth credentials are stored in right place"""
    response = client.get("/get", params={"APIKEY": auth.api_key})
    if credentials == "queryString":
        assert response.status_code == 200
    else:
        assert response.status_code == 401


def test_cookie(hostname, auth, credentials):
    """Test if auth credentials are stored in right place"""
    with hostname.client(cookies={"APIKEY": auth.api_key}) as client:
        response = client.get("/get")
        if credentials == "cookie":
            assert response.status_code == 200
        else:
            assert response.status_code == 401
