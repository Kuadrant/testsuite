"""Conftest for Open Policy Agent (OPA)"""
import pytest
from dynaconf import ValidationError

from testsuite.mockserver import Mockserver
from testsuite.utils import rego_allow_header


@pytest.fixture(scope="module")
def header():
    """Header used by OPA policy"""
    return "opa", "opa-test"


@pytest.fixture(scope="module")
def mockserver(request, testconfig, module_label, header):
    """Returns mockserver and creates Expectation that returns Rego query"""
    try:
        testconfig.validators.validate(only=["mockserver"])
        mockserver = Mockserver(testconfig["mockserver"]["url"])
        request.addfinalizer(lambda: mockserver.clear_expectation(module_label))
        mockserver.create_expectation(module_label, "/opa", rego_allow_header(*header))
        return mockserver
    except (KeyError, ValidationError) as exc:
        return pytest.skip(f"Mockserver configuration item is missing: {exc}")
