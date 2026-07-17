"""Fixtures for PipelinePolicy interaction tests with AuthPolicy and RateLimitPolicy."""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy.rate_limit import Limit


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """AuthPolicy with OIDC identity verification."""
    authorization.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Valid OIDC authentication for requests."""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """RateLimitPolicy with a low limit for testing."""
    rate_limit.add_limit("basic", [Limit(3, "10s")])
    return rate_limit
