"""Tests for Open Policy Agent (OPA) using Mockserver Expectations as http endpoint with Rego query"""

import pytest


@pytest.fixture(scope="module")
def authorization(mockserver, authorization):
    """
    Adds OPA policy. Rego query is located on external registry (Mockserver).
    Policy accepts requests that contain `header`.
    """
    authorization.add_external_opa_policy("opa", mockserver.url + "/opa")
    return authorization


def test_allowed_by_opa(client, auth, header):
    """Tests a request that should be authorized by OPA external registry declaration"""
    key, value = header
    response = client.get("/get", auth=auth, headers={key: value})
    assert response.status_code == 200


def test_denied_by_opa(client, auth):
    """Tests a request should be denied by OPA external registry declaration"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 403
