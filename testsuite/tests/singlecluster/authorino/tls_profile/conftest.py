"""Conftest for TLS security profile propagation tests"""

import pytest

from testsuite.gateway.exposers import OpenShiftExposer
from testsuite.kubernetes.openshift.route import OpenshiftRoute
from testsuite.kubernetes.secret import TLSSecret


@pytest.fixture(scope="module", autouse=True)
def commit(kuadrant, exposer, skip_or_fail):
    """No policies to commit for TLS profile tests"""
    if not kuadrant:
        skip_or_fail("Test requires Kuadrant")
    if not isinstance(exposer, OpenShiftExposer):
        skip_or_fail("Test requires OpenShift cluster to access the APIServer CR configuration")


@pytest.fixture(scope="module")
def tls_cert(request, cfssl, authorino, system_project, blame):
    """CFSSL-generated TLS certificate for Authorino servers"""
    cert_name = blame("tls")
    certificate = cfssl.create("authorino-tls", hosts=[authorino.oidc_url, authorino.authorization_url])
    tls_secret = TLSSecret.create_instance(system_project, cert_name, certificate)
    request.addfinalizer(tls_secret.delete)
    tls_secret.commit()
    return cert_name


@pytest.fixture(scope="module")
def configure_authorino_tls(request, kuadrant, authorino, tls_cert):  # pylint: disable=unused-argument
    """Enables TLS on Authorino CR using the CFSSL-generated certificate"""
    original_listener_tls = dict(authorino.model.spec.get("listener", {}).get("tls", {}))
    original_oidc_tls = dict(authorino.model.spec.get("oidcServer", {}).get("tls", {}))

    def _restore_tls(obj):
        obj.model.spec["listener"]["tls"] = original_listener_tls
        obj.model.spec["oidcServer"]["tls"] = original_oidc_tls

    request.addfinalizer(lambda: authorino.apply(_restore_tls))

    def _enable_tls(obj):
        tls_config = {"enabled": True, "certSecretRef": {"name": tls_cert}}
        obj.model.spec["listener"]["tls"] = tls_config
        obj.model.spec["oidcServer"]["tls"] = tls_config

    authorino.apply(_enable_tls)

    authorino.deployment.wait_for_ready()


@pytest.fixture(scope="module")
def tls_profile(request, cluster, authorino, configure_authorino_tls):  # pylint: disable=unused-argument
    """Sets the APIServer TLS profile and waits for Authorino propagation"""
    profile_type, min_version, ciphers = request.param
    api_server = cluster.api_server_cr

    original_profile = api_server.tls_profile_type
    request.addfinalizer(lambda: api_server.set_tls_profile(original_profile))
    ocp_version = f"VersionTLS{min_version.replace('.', '')}" if ciphers else None
    api_server.set_tls_profile(profile_type, min_version=ocp_version, ciphers=ciphers)

    assert authorino.wait_until(
        lambda obj: obj.model.spec.get("listener", {}).get("tls", {}).get("minVersion") == min_version
    ), f"Authorino CR TLS config was not updated for {profile_type} profile within 60s"
    authorino.deployment.wait_for_ready()


@pytest.fixture(scope="module")
def oidc_route(request, authorino, system_project, blame):
    """Passthrough Route exposing Authorino OIDC endpoint for direct TLS probing"""
    route = OpenshiftRoute.create_instance(
        system_project,
        blame("oidc"),
        authorino.oidc_url.split(".")[0],
        target_port="http",
        tls=True,
        termination="passthrough",
    )
    request.addfinalizer(route.delete)
    route.commit()
    return route


@pytest.fixture(scope="module")
def authorization_route(request, authorino, system_project, blame):
    """Passthrough Route exposing Authorino authorization endpoint for direct TLS probing"""
    route = OpenshiftRoute.create_instance(
        system_project,
        blame("auth"),
        authorino.authorization_url.split(".")[0],
        target_port="grpc",
        tls=True,
        termination="passthrough",
    )
    request.addfinalizer(route.delete)
    route.commit()
    return route
