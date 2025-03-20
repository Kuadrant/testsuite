"""Conftest for merge strategy tests for same target for auth policies"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth, HeaderApiKeyAuth
from testsuite.kuadrant.policy import Strategy
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy


@pytest.fixture(scope="module")
def api_key(create_api_key, module_label):
    """Creates API key Secret"""
    return create_api_key("api-key", module_label, "api_key_value")


@pytest.fixture(scope="module")
def authorization(cluster, blame, module_label, route, oidc_provider):
    """Create an AuthPolicy with a basic limit with same target as one default."""
    auth_policy = AuthPolicy.create_instance(cluster, blame("sp"), route, labels={"testRun": module_label})
    auth_policy.identity.add_oidc("basic", oidc_provider.well_known["issuer"])
    return auth_policy


@pytest.fixture(scope="module")
def default_merge_authorization(cluster, blame, module_label, route, api_key):
    """Create a AuthPolicy with default policies and a merge strategy."""
    auth_policy = AuthPolicy.create_instance(cluster, blame("dmp"), route, labels={"testRun": module_label})
    auth_policy.defaults.identity.add_anonymous("basic")
    auth_policy.defaults.identity.add_api_key("merge", selector=api_key.selector)
    auth_policy.defaults.strategy(Strategy.MERGE)
    return auth_policy


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns Authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def merge_auth(api_key):
    """Valid API Key Auth"""
    return HeaderApiKeyAuth(api_key)
