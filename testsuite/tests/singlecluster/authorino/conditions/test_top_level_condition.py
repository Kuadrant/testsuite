"""Test condition to skip the entire AuthConfig"""

import pytest

from testsuite.kuadrant.policy import CelPredicate

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization, module_label):
    """Add rule to the AuthConfig to skip entire authn/authz with certain request header"""
    authorization.add_rule([CelPredicate(f"!(has(request.headers.key) && request.headers.key == '{module_label}')")])
    return authorization


def test_skip_auth_config(client, auth, module_label):
    """
    Send requests with and without required header,
    verify that header request trigger skip of entire AuthConfig
    """
    # header request ignores oidc identity
    response = client.get("/get", headers={"key": module_label})
    assert response.status_code == 200

    # request without header uses AuthConfig
    response = client.get("/get")
    # request is rejected due to the oidc authentication absence
    assert response.status_code == 401

    # when oidc authentication is provided on a request without required header, request is accepted
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
