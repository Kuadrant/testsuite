"""Tests for Open Policy Agent (OPA) Rego policies"""

import pytest

from testsuite.utils import rego_allow_header


@pytest.fixture(scope="module")
def header():
    """Header used by OPA policy"""
    return "opa", "opa-test"


@pytest.fixture(scope="module")
def authorization(authorization, header):
    """Adds OPA policy that accepts all requests that contain `header`"""
    authorization.authorization.add_opa_policy("opa", rego_allow_header(*header))
    return authorization


def test_authorized_by_opa(client, auth, header):
    """Tests a request that should be authorized by OPA"""
    key, value = header
    response = client.get("/get", auth=auth, headers={key: value})
    assert response.status_code == 200


def test_rejected_by_opa(client, auth):
    """Tests a request that does not have the correct header for OPA policy"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 403
