"""
Tests for Open Policy Agent (OPA) policy pulled from external registry.
Registry is represented by Mockserver Expectation that returns Rego query.
"""

from time import sleep

import pytest

from testsuite.utils import rego_allow_header


pytestmark = [pytest.mark.authorino]


KEY = "test-key"
VALUE = "test-value"


@pytest.fixture(scope="function", autouse=True)
def reset_expectation(mockserver, module_label):
    """Updates Expectation with updated header"""
    mockserver.create_response_expectation(module_label, rego_allow_header(KEY, VALUE))
    sleep(2)  # waits for cache to reset because of ttl=1


def test_caching(client, auth, mockserver, blame, module_label):
    """Tests that external policy is cached"""
    response = client.get("/get", auth=auth, headers={KEY: VALUE})
    assert response.status_code == 200

    mockserver.create_response_expectation(module_label, rego_allow_header(blame(KEY), blame(VALUE)))

    response = client.get("/get", auth=auth, headers={KEY: VALUE})
    assert response.status_code == 200


def test_cache_refresh(client, auth, mockserver, blame, module_label):
    """Tests that policy is pull again from external registry after ttl expiration"""
    response = client.get("/get", auth=auth, headers={KEY: VALUE})
    assert response.status_code == 200

    mockserver.create_response_expectation(module_label, rego_allow_header(blame(KEY), blame(VALUE)))
    sleep(2)

    response = client.get("/get", auth=auth, headers={KEY: VALUE})
    assert response.status_code == 403
