"""Conftest for merge strategy tests for same target for auth policies"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy import Strategy
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.oidc import OIDCProvider
from testsuite.oidc.keycloak import Keycloak


@pytest.fixture(scope="module")
def merge_oidc_provider(request, blame, keycloak) -> OIDCProvider:
    """Fixture that will create an OIDC provider with a new realm that will be used as default in an auth policy"""
    realm_name = blame("realm")
    request.addfinalizer(lambda: keycloak.master_realm.delete_realm(realm_name))
    k = Keycloak(
        keycloak.server_url,
        keycloak.username,
        keycloak.password,
        realm_name,
        "base-client",
    )
    k.commit()
    return k


@pytest.fixture(scope="module")
def merge_oidc_provider_2(request, blame, keycloak) -> OIDCProvider:
    """Fixture that will create an OIDC provider with a new realm that will be used as default in an auth policy"""
    realm_name = blame("realm")
    request.addfinalizer(lambda: keycloak.master_realm.delete_realm(realm_name))
    k = Keycloak(
        keycloak.server_url,
        keycloak.username,
        keycloak.password,
        realm_name,
        "base-client",
    )
    k.commit()
    return k


@pytest.fixture(scope="module")
def authorization(cluster, blame, module_label, route, oidc_provider):
    """Create an AuthPolicy with a basic limit with same target as one default."""
    auth_policy = AuthPolicy.create_instance(cluster, blame("sp"), route, labels={"testRun": module_label})
    auth_policy.identity.add_oidc("basic", oidc_provider.well_known["issuer"])
    return auth_policy


@pytest.fixture(scope="module")
def default_merge_authorization(cluster, blame, module_label, route, merge_oidc_provider, merge_oidc_provider_2):
    """Create a AuthPolicy with default policies and a merge strategy."""
    auth_policy = AuthPolicy.create_instance(cluster, blame("dmp"), route, labels={"testRun": module_label})
    auth_policy.defaults.identity.add_oidc("basic", merge_oidc_provider.well_known["issuer"])
    auth_policy.defaults.identity.add_oidc("merge", merge_oidc_provider_2.well_known["issuer"])
    auth_policy.defaults.strategy(Strategy.MERGE)
    return auth_policy


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns Authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def merge_auth(merge_oidc_provider):
    """Returns Authentication object for HTTPX for the global AuthPolicy"""
    return HttpxOidcClientAuth(merge_oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def merge_auth_2(merge_oidc_provider_2):
    """Returns Authentication object for HTTPX for the global AuthPolicy"""
    return HttpxOidcClientAuth(merge_oidc_provider_2.get_token, "authorization")
