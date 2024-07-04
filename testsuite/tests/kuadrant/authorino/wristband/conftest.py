"""Conftest for Edge Authentication tests"""

import pytest

from testsuite.certificates import CertInfo
from testsuite.policy.authorization import WristbandSigningKeyRef, WristbandResponse
from testsuite.policy.authorization.auth_config import AuthConfig
from testsuite.gateway.envoy.route import EnvoyVirtualRoute
from testsuite.gateway.envoy.wristband import WristbandEnvoy
from testsuite.kubernetes.secret import TLSSecret
from testsuite.utils import cert_builder


@pytest.fixture(scope="session")
def oidc_provider(keycloak):
    """Fixture which enables switching out OIDC providers for individual modules"""
    return keycloak


@pytest.fixture(scope="module")
def wristband_secret(blame, request, cluster, certificates) -> str:
    """Create signing wristband secret"""
    wristband_secret_name = blame("wristband-signing-key")
    secret = TLSSecret.create_instance(
        cluster, wristband_secret_name, certificates["signing_ca"], "cert.pem", "key.pem", "Opaque"
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
def gateway(request, authorino, cluster, blame, module_label, testconfig):
    """Deploys Envoy with additional edge-route match"""
    envoy = WristbandEnvoy(
        cluster,
        blame("gw"),
        authorino,
        testconfig["service_protection"]["envoy"]["image"],
        labels={"app": module_label},
    )
    request.addfinalizer(envoy.delete)
    envoy.commit()
    return envoy


@pytest.fixture(scope="module")
def wristband_name(blame):
    """Name of the wristband response Authorization"""
    return blame("auth-wristband")


@pytest.fixture(scope="module")
def wristband_endpoint(cluster, authorino, wristband_name):
    """Authorino oidc wristband endpoint"""
    return f"http://{authorino.oidc_url}:8083/{cluster.project}/{wristband_name}/wristband"


@pytest.fixture(scope="module")
def authorization(authorization, wristband_endpoint) -> AuthConfig:
    """Add wristband authentication to Authorization"""
    authorization.identity.clear_all()
    authorization.identity.add_oidc("edge-authenticated", wristband_endpoint)
    return authorization


@pytest.fixture(scope="module")
def wristband_token(wristband_hostname, auth):
    """Test token acquirement from oidc endpoint"""
    with wristband_hostname.client() as client:
        response = client.get("/auth", auth=auth)
        assert response.status_code == 200

        assert response.headers.get("wristband-token") is not None
        return response.headers["wristband-token"]


@pytest.fixture(scope="module")
def wristband_hostname(exposer, gateway, blame):
    """Hostname on which you can acquire wristband token"""
    return exposer.expose_hostname(blame("route"), gateway)


@pytest.fixture(scope="module")
def wristband_authorization(
    request,
    gateway,
    wristband_name,
    oidc_provider,
    wristband_hostname,
    label,
    wristband_endpoint,
    wristband_secret,
):
    """Second AuthConfig with authorino oidc endpoint for getting the wristband token"""
    route = EnvoyVirtualRoute.create_instance(gateway.openshift, wristband_name, gateway)
    route.add_hostname(wristband_hostname.hostname)

    request.addfinalizer(route.delete)
    route.commit()

    authorization = AuthConfig.create_instance(
        gateway.openshift,
        wristband_name,
        route,
        labels={"testRun": label},
    )

    authorization.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    authorization.responses.add_success_dynamic(
        "wristband",
        WristbandResponse(issuer=wristband_endpoint, signingKeyRefs=[WristbandSigningKeyRef(wristband_secret)]),
    )
    return authorization


@pytest.fixture(scope="module", autouse=True)
def commit(request, commit, wristband_authorization):  # pylint: disable=unused-argument
    """Commits all important stuff before tests"""
    request.addfinalizer(wristband_authorization.delete)
    wristband_authorization.commit()
    wristband_authorization.wait_for_ready()
