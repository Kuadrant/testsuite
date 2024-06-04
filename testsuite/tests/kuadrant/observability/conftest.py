"""Conftest for Kuadrant observability tests"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.openshift.authorino import TracingOptions
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


@pytest.fixture(scope="module", autouse=True)
def enable_tracing(authorino, limitador, tracing):
    """Enable tracing for Authorino and Limitador"""
    authorino["tracing"] = TracingOptions(tracing.collector_url, insecure=True)
    authorino.safe_apply()
    authorino.wait_for_ready()

    limitador.refresh()  # limitador is not up-to-date, as limit from RLP is added to LimitadorCR
    limitador["tracing"] = TracingOptions(tracing.collector_url)
    limitador.safe_apply()
    limitador.wait_for_ready()
