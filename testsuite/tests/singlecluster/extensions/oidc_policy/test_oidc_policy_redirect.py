"""Tests for OIDCPolicy redirect handling bug fixes (kuadrant-operator#2017).

Validates fixes for:
- Bug 1: Port dropped from auto-constructed redirect URI when listener uses non-standard port
- Bug 2: OPA cookie parser breaks on '=' in values (indirectly tested via query string test)
- Bug 3: Target cookie drops query string after OIDC auth redirect
"""

from urllib.parse import unquote

import pytest

from keycloak import KeycloakOpenID

from testsuite.gateway import GatewayListener
from testsuite.gateway.exposers import StaticLocalHostname
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.oidc.keycloak.objects import ClientConfig
from testsuite.tests.singlecluster.extensions.oidc_policy.conftest import set_jwt_cookie

pytestmark = [
    pytest.mark.authorino,
    pytest.mark.kuadrant_only,
    pytest.mark.extensions,
    pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/2017"),
]

CUSTOM_PORT = 8001


@pytest.fixture(scope="module")
def gateway(request, domain_name, base_domain, cluster, blame, label):
    """Gateway with a non-standard listener port to test port inclusion in redirect URI."""
    fqdn = f"{domain_name}-{cluster.project}.{base_domain}"
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": label})
    gw.add_listener(GatewayListener(hostname=fqdn, port=CUSTOM_PORT))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def hostname(gateway, domain_name, cluster, exposer):
    """Hostname that connects on the non-standard gateway port."""
    fqdn = f"{domain_name}-{cluster.project}.{exposer.base_domain}"
    ip = gateway.refresh().model.status.addresses[0].value

    return StaticLocalHostname(fqdn, lambda: f"{ip}:{CUSTOM_PORT}")


@pytest.fixture(scope="module")
def keycloak_client(keycloak, hostname, blame):
    """Create confidential OIDC client on Keycloak."""
    config = ClientConfig(
        client_id=blame("redirect"),
        public_client=False,
        redirect_uris=[f"http://{hostname.hostname}/*"],
        web_origins=[f"http://{hostname.hostname}"],
        root_url=f"http://{hostname.hostname}",
        service_accounts_enabled=True,
    )
    kc_client = keycloak.realm.create_client(**config.to_keycloak_payload())
    return KeycloakOpenID(
        server_url=keycloak.server_url,
        client_id=kc_client.auth_id,
        realm_name=keycloak.realm_name,
        client_secret_key=kc_client.secret,
    )


def test_redirect_uri_includes_listener_port(client, gateway):
    """Auto-constructed redirect URI must include the non-standard listener port."""
    response = client.get("/")
    assert response.status_code == 302

    location = unquote(response.headers["Location"])
    gw_hostname = gateway.model.spec.listeners[0].hostname
    expected = f"redirect_uri=http://{gw_hostname}:{CUSTOM_PORT}/auth/callback"
    assert expected in location, f"redirect_uri should include port {CUSTOM_PORT}, got: {location}"


def test_query_string_preserved_in_target_cookie(client):
    """Target cookie must include query string parameters from the original request."""
    response = client.get("/get?foo=bar&baz=qux")
    assert response.status_code == 302

    set_cookie_headers = response.headers.get_list("set-cookie")
    target_cookies = [c for c in set_cookie_headers if c.startswith("target=")]
    assert target_cookies, "Response should set a 'target' cookie"

    target_value = target_cookies[0].split(";")[0]
    assert (
        target_value == "target=/get?foo=bar&baz=qux"
    ), f"Target cookie should include query string, got: {target_value}"


def test_authenticated_request_with_query_params(client, auth):
    """Authenticated requests with query parameters should succeed."""
    with set_jwt_cookie(client, auth.access_token):
        response = client.get("/get?foo=bar")
        assert response.status_code == 200
