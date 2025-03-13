"""Test gateway level default merging with and being partially overriden by another policy."""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit, Strategy
from testsuite.oidc import OIDCProvider
from testsuite.oidc.keycloak import Keycloak

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]

@pytest.fixture(scope="module")
def global_oidc_provider(request, blame, keycloak) -> OIDCProvider:
    realm_name = blame("realm")
    request.addfinalizer(lambda : keycloak.master_realm.delete_realm(realm_name))
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
def authorization(authorization, oidc_provider):
    """Create an AuthPolicy with a basic limit with same target as one default."""
    authorization.identity.add_oidc("a", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def global_authorization(cluster, blame, module_label, gateway, global_oidc_provider):
    """Create a AuthPolicy with default policies and a merge strategy."""
    global_auth_policy = AuthPolicy.create_instance(
        cluster, blame("authz"), gateway, labels={"testRun": module_label}
    )
    global_auth_policy.defaults.strategy(Strategy.MERGE)
    global_auth_policy.defaults.identity.add_oidc("global", global_oidc_provider.well_known["issuer"])
    return global_auth_policy


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns Authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def global_auth(global_oidc_provider):
    """Returns Authentication object for HTTPX for the global Auth Policy"""
    return HttpxOidcClientAuth(global_oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, authorization, global_authorization):  # pylint: disable=unused-argument
    """Commits RateLimitPolicy after the HTTPRoute is created"""
    for policy in [global_authorization, authorization]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_ready()


@pytest.mark.parametrize("authorization", ["gateway", "route"], indirect=True)
def test_gateway_default_merge(client, global_authorization, auth, global_auth):
    """Test Gateway default policy being partially overriden when another policy with the same target is created."""
    assert client.get("/get").status_code == 401
    assert client.get("/get", auth=global_auth).status_code == 200
    assert client.get("/get", auth=auth).status_code == 200  # assert that AuthPolicy is enforced


