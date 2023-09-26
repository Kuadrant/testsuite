"""Conftest for Edge Authentication tests"""

import pytest

from testsuite.certificates import CertInfo
from testsuite.objects import WristbandResponse, WristbandSigningKeyRef
from testsuite.openshift.objects.auth_config import AuthConfig
from testsuite.openshift.objects.envoy.route import EnvoyVirtualRoute
from testsuite.openshift.objects.envoy.wristband import WristbandEnvoy
from testsuite.openshift.objects.secret import TLSSecret
from testsuite.utils import cert_builder


@pytest.fixture(scope="module")
def run_on_kuadrant():
    """Kuadrant doesn't allow customization of Authorino parameters"""
    return False


@pytest.fixture(scope="session")
def oidc_provider(rhsso):
    """Fixture which enables switching out OIDC providers for individual modules"""
    return rhsso


@pytest.fixture(scope="module")
def wristband_secret(blame, request, openshift, certificates) -> str:
    """Create signing wristband secret"""
    wristband_secret_name = blame("wristband-signing-key")
    secret = TLSSecret.create_instance(
        openshift, wristband_secret_name, certificates["signing_ca"], "cert.pem", "key.pem", "Opaque"
    )
    request.addfinalizer(secret.delete)
    secret.commit()
    return wristband_secret_name


@pytest.fixture(scope="module")
def certificates(cfssl, wildcard_domain):
    """Certificate hierarchy used for the wristband tests"""
    chain = {
        "signing_ca": CertInfo(ca=True),
    }
    return cert_builder(cfssl, chain, wildcard_domain)


@pytest.fixture(scope="module")
def gateway(request, authorino, openshift, blame, module_label, testconfig):
    """Deploys Envoy with additional edge-route match"""
    envoy = WristbandEnvoy(
        openshift,
        blame("gw"),
        authorino,
        testconfig["service_protection"]["envoy"]["image"],
        labels={"app": module_label},
    )
    request.addfinalizer(envoy.delete)
    envoy.commit()
    return envoy


@pytest.fixture(scope="module")
def wristband_endpoint(openshift, authorino, authorization_name):
    """Authorino oidc wristband endpoint"""
    return f"http://{authorino.oidc_url}:8083/{openshift.project}/{authorization_name}/wristband"


@pytest.fixture(scope="module")
def authorization(authorization, wristband_secret, wristband_endpoint) -> AuthConfig:
    """Add wristband response with the signing key to the AuthConfig"""

    authorization.responses.add_success_dynamic(
        "wristband",
        WristbandResponse(issuer=wristband_endpoint, signingKeyRefs=[WristbandSigningKeyRef(wristband_secret)]),
    )
    return authorization


@pytest.fixture(scope="module")
def wristband_token(client, auth):
    """Test token acquirement from oidc endpoint"""
    response = client.get("/auth", auth=auth)
    assert response.status_code == 200

    assert response.headers.get("wristband-token") is not None
    return response.headers["wristband-token"]


@pytest.fixture(scope="module")
def authenticated_route(exposer, gateway, blame):
    """Second envoy route, intended for the already authenticated user"""
    return exposer.expose_hostname(blame("route"), gateway)


@pytest.fixture(scope="module")
def authenticated_authorization(request, gateway, blame, authenticated_route, module_label, wristband_endpoint):
    """Second AuthConfig with authorino oidc endpoint, protecting route for the already authenticated user"""
    route = EnvoyVirtualRoute.create_instance(gateway.openshift, blame("route"), gateway)
    route.add_hostname(authenticated_route.hostname)

    request.addfinalizer(route.delete)
    route.commit()

    authorization = AuthConfig.create_instance(
        gateway.openshift,
        blame("auth-authenticated"),
        route,
        labels={"testRun": module_label},
    )
    authorization.identity.add_oidc("edge-authenticated", wristband_endpoint)
    return authorization


@pytest.fixture(scope="module")
def authenticated_client(authenticated_route):
    """Client with route for the already authenticated user"""
    client = authenticated_route.client()
    yield client
    client.close()


# pylint: disable=unused-argument
@pytest.fixture(scope="module", autouse=True)
def commit(request, commit, authenticated_authorization):
    """Commits all important stuff before tests"""
    request.addfinalizer(authenticated_authorization.delete)
    authenticated_authorization.commit()
