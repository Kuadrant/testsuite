"""Test gateway level default merging with and being partially overriden by another policy."""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth, HeaderApiKeyAuth
from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import Strategy
from testsuite.kubernetes.api_key import APIKey
from testsuite.kubernetes.client import KubernetesClient

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino]


@pytest.fixture(scope="module")
def create_api_key(blame, request, cluster):
    """Creates API key Secret"""

    def _create_secret(name, label_selector, api_key, ocp: KubernetesClient = cluster):
        secret_name = blame(name)
        secret = APIKey.create_instance(ocp, secret_name, label_selector, api_key)
        request.addfinalizer(lambda: secret.delete(ignore_not_found=True))
        secret.commit()
        return secret

    return _create_secret


@pytest.fixture(scope="module")
def api_key(create_api_key, module_label):
    """Creates API key Secret"""
    return create_api_key("api-key", module_label, "api_key_value")


@pytest.fixture(scope="module")
def authorization(authorization, api_key):
    """Create an AuthPolicy with a basic limit with same target as one default."""
    authorization.identity.add_api_key("route_auth", selector=api_key.selector)
    return authorization


@pytest.fixture(scope="module")
def global_authorization(cluster, blame, module_label, gateway, oidc_provider, api_key):
    """Create a AuthPolicy with default policies and a merge strategy."""
    global_auth_policy = AuthPolicy.create_instance(cluster, blame("authz"), gateway, labels={"testRun": module_label})
    global_auth_policy.defaults.strategy(Strategy.MERGE)
    global_auth_policy.defaults.identity.add_oidc("route_auth", oidc_provider.well_known["issuer"])
    global_auth_policy.defaults.identity.add_api_key("gateway_auth", selector=api_key.selector)
    return global_auth_policy


@pytest.fixture(scope="module")
def auth(api_key):
    """Valid API Key Auth"""
    return HeaderApiKeyAuth(api_key)


@pytest.fixture(scope="module")
def global_auth(oidc_provider):
    """Returns Authentication object for HTTPX for the global AuthPolicy"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, authorization, global_authorization):  # pylint: disable=unused-argument
    """Commits AuthPolicy after the HTTPRoute is created"""
    for policy in [global_authorization, authorization]:  # Forcing order of creation.
        request.addfinalizer(policy.delete)
        policy.commit()
        policy.wait_for_ready()


@pytest.mark.parametrize("authorization", ["gateway", "route"], indirect=True)
def test_gateway_default_merge(client, global_authorization, auth, global_auth):
    """Test Gateway default policy being partially overriden when another policy with the same target is created."""
    assert global_authorization.wait_until(
        has_condition("Enforced", "True", "Enforced", "AuthPolicy has been partially enforced")
    )

    assert client.get("/get").status_code == 401
    assert client.get("/get", auth=global_auth).status_code == 401
    assert client.get("/get", auth=auth).status_code == 200  # assert that AuthPolicy is enforced
