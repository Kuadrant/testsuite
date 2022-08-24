"""Conftest for auth tests"""
import http.client
import json

import pytest

from testsuite.config import settings
from testsuite.httpx.auth import Auth0Auth


@pytest.fixture(scope="module")
def auth0_token():
    """Token for Auth0 API"""
    try:
        auth = settings["auth0"]
        conn = http.client.HTTPSConnection(auth['domain'])
        payload = '{' + f"\"client_id\":\"{auth['client']}\"," \
                        f"\"client_secret\":\"{auth['client-secret']}\"," \
                        f"\"audience\":\"https://{auth['domain']}/api/v2/\",\"grant_type\":\"client_credentials\"" + '}'
        headers = {'content-type': "application/json"}
        conn.request("POST", "/oauth/token", payload, headers)
        res = conn.getresponse()
        data = res.read()
        return json.loads(data.decode("utf-8"))["access_token"]
    except KeyError as exc:
        return pytest.skip(f"Auth0 configuration item is missing: {exc}")


@pytest.fixture(scope="module")
def auth0_authorization(authorization):
    """Add Auth0 identity to AuthConfig"""
    try:
        authorization.add_oidc_identity("auth", f"https://{settings['auth0']['domain']}/")
        return authorization
    except KeyError as exc:
        return pytest.skip(f"Auth0 domain configuration is missing: {exc}")


@pytest.fixture(scope="module")
def auth0_auth(auth0_token):
    """Returns Auth0 authentication object for HTTPX"""
    return Auth0Auth(auth0_token)


@pytest.fixture(scope="module")
def rhsso_authorization(authorization, rhsso_service_info):
    """Add RHSSO identity to AuthConfig"""
    authorization.add_oidc_identity("rhsso", rhsso_service_info.issuer_url())
    return authorization


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def auth0_client(auth0_authorization, envoy):
    """Returns httpx client to be used for requests, it also commits AuthConfig"""
    client = envoy.client()
    yield client
    client.close()


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def rhsso_client(rhsso_authorization, envoy):
    """Returns httpx client to be used for requests, it also commits AuthConfig"""
    client = envoy.client()
    yield client
    client.close()
