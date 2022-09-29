"""
Tests for Open Policy Agent (OPA) policy pulled from external registry.
Registry is represented by Mockserver Expectation that returns Rego query.
"""
import time

import pytest

from testsuite.utils import rego_allow_header


@pytest.fixture(scope="module")
def updated_header():
    """Header for updated OPA policy"""
    return "updated", "updated-value"


@pytest.fixture(scope="module", autouse=True)
def update_external_opa(mockserver, module_label, updated_header):
    """Updates Expectation with updated header"""
    mockserver.create_expectation(module_label, f"/{module_label}/opa", rego_allow_header(*updated_header))
    # Sleeps for 1 second to compensate auto-refresh cycle `authorization.opa.externalRegistry.ttl = 1`
    time.sleep(1)


def test_auto_refresh(client, auth, updated_header):
    """Tests auto-refresh of OPA policy from external registry."""
    key, value = updated_header
    response = client.get("/get", auth=auth, headers={key: value})
    assert response.status_code == 200


def test_previous(client, auth, header):
    """Tests invalidation of previous OPA policy"""
    key, value = header
    response = client.get("/get", auth=auth, headers={key: value})
    assert response.status_code == 403
