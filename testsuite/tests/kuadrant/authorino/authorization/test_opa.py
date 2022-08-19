"""Tests for Open Policy Agent (OPA) Rego policies"""
import pytest


@pytest.fixture(scope="module")
def header():
    """Header used by OPA policy"""
    return "opa", "opa-test"


@pytest.fixture(scope="module")
def authorization(authorization, header):
    """
    Creates AuthConfig with API key identity and configures it with OPA policy
    that accepts only those requests that contain header correct header
    """
    key, value = header
    rego_inline = f"allow {{ input.context.request.http.headers.{key} == \"{value}\" }}"
    authorization.add_opa_policy("opa", rego_inline)
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
