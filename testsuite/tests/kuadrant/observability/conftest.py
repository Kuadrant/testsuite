"""Conftest for Kuadrant observability tests"""

import pytest
from openshift_client import OpenShiftPythonException
from openshift_client import selector

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.openshift.authorino import TracingOptions
from testsuite.openshift.limitador import LimitadorCR
from testsuite.policy.rate_limit_policy import Limit


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns RHSSO authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    rate_limit.add_limit("basic", [Limit(5, 60)])
    return rate_limit


@pytest.fixture(scope="session")
def limitador(system_openshift) -> LimitadorCR:
    """Returns Limitador CR"""
    try:
        with system_openshift.context:
            limitador = selector("limitador").object(cls=LimitadorCR)
            limitador.committed = True
    except OpenShiftPythonException:
        pytest.fail("Running Kuadrant tests, but Limitador resource was not found")

    return limitador


@pytest.fixture(scope="module", autouse=True)
def enable_tracing(authorino, limitador, tracing):
    """Enable tracing for Authorino and Limitador"""
    authorino.tracing = TracingOptions(tracing.collector_url, insecure=True)
    limitador.tracing = TracingOptions(tracing.collector_url)
    limitador.verbosity = 3
    limitador.deployment.wait_for_ready()
