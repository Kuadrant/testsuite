"""Conftest for Edge Authentication tests"""
from importlib import resources

import pytest

from testsuite.openshift.objects.auth_config import AuthConfig
from testsuite.openshift.envoy import Envoy
from testsuite.certificates import CertInfo
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
    secret = openshift.create_tls_secret(
        wristband_secret_name, certificates["signing_ca"], "cert.pem", "key.pem", "Opaque"
    )
    request.addfinalizer(lambda: openshift.delete_selector(secret))
    return wristband_secret_name


@pytest.fixture(scope="session")
def certificates(cfssl, wildcard_domain):
    """Certificate hierarchy used for the wristband tests"""
    chain = {
        "signing_ca": CertInfo(ca=True),
    }
    return cert_builder(cfssl, chain, wildcard_domain)


@pytest.fixture(scope="module")
def envoy(request, authorino, openshift, blame, backend, module_label, testconfig):
    """Deploys Envoy with additional edge-route match"""
    wristband_envoy = resources.files("testsuite.resources.wristband").joinpath("envoy.yaml")
    envoy = Envoy(
        openshift, authorino, blame("envoy"), module_label, backend, testconfig["envoy"]["image"], wristband_envoy
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
    authorization.responses.wristband("wristband", wristband_endpoint, wristband_secret, wrapper="envoyDynamicMetadata")
    return authorization


@pytest.fixture(scope="module")
def wristband_token(client, auth):
    """Test token acquirement from oidc endpoint"""
    response = client.get("/auth", auth=auth)
    assert response.status_code == 200

    assert response.headers.get("wristband-token") is not None
    return response.headers["wristband-token"]


@pytest.fixture(scope="module")
def hostname_authenticated(envoy, blame):
    """Second envoy route, intended for the already authenticated user"""
    return envoy.add_hostname(blame("route-authenticated"))


@pytest.fixture(scope="module")
def authorization_authenticated(openshift, blame, hostname_authenticated, module_label, wristband_endpoint):
    """Second AuthConfig with authorino oidc endpoint, protecting route for the already authenticated user"""
    authorization = AuthConfig.create_instance(
        openshift,
        blame("auth-authenticated"),
        None,
        hostnames=[hostname_authenticated],
        labels={"testRun": module_label},
    )
    authorization.identity.oidc("edge-authenticated", wristband_endpoint)
    return authorization


@pytest.fixture(scope="module")
def client_authenticated(hostname_authenticated, envoy):
    """Client with route for the already authenticated user"""
    client = envoy.client()
    client.base_url = f"http://{hostname_authenticated}"
    yield client
    client.close()


# pylint: disable=unused-argument
@pytest.fixture(scope="module", autouse=True)
def commit(request, commit, authorization_authenticated):
    """Commits all important stuff before tests"""
    request.addfinalizer(authorization_authenticated.delete)
    authorization_authenticated.commit()
