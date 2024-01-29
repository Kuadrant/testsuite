"""Conftest for OPA policy located on external registry"""

import pytest

from testsuite.utils import rego_allow_header


@pytest.fixture(scope="module")
def header():
    """Header used by OPA policy"""
    return "opa", "opa-test"


@pytest.fixture(scope="module")
def opa_policy_expectation(request, mockserver, module_label, header):
    """Creates Mockserver Expectation that returns Rego query and returns its endpoint"""
    request.addfinalizer(lambda: mockserver.clear_expectation(module_label))
    return mockserver.create_expectation(module_label, rego_allow_header(*header))


@pytest.fixture(scope="module")
def authorization(authorization, opa_policy_expectation):
    """
    Adds OPA policy. Rego query is located on external registry (Mockserver).
    Policy accepts requests that contain `header`.
    """
    authorization.authorization.add_external_opa_policy("opa", opa_policy_expectation, 1)
    return authorization
