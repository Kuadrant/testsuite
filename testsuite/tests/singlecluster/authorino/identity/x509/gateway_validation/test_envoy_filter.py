"""Tests for x509 client certificate authentication using EnvoyFilter.
Tier 2 from RFC 0015 - https://github.com/Kuadrant/architecture/blob/main/rfcs/0015-x509-client-cert-authpolicy.md

This implements the workaround from https://github.com/Kuadrant/architecture/issues/140
where client certificate validation is enabled at the gateway level using an Istio EnvoyFilter,
and AuthPolicy with x509 identity to extract and validate the client certificate
from the X-Forwarded-Client-Cert (XFCC) header.
"""

import pytest

from testsuite.gateway import TLSGatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.kubernetes.deployment import SecretVolume, VolumeMount
from testsuite.kubernetes.envoy_filter import EnvoyFilter
from testsuite.kubernetes.secret import Secret

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, wildcard_domain, module_label):
    """Gateway with TLS listener without frontend validation (EnvoyFilter handles L4 validation)"""
    gateway_name = blame("gw")
    gw = KuadrantGateway.create_instance(cluster, gateway_name, labels={"app": module_label})
    gw.add_listener(TLSGatewayListener(hostname=wildcard_domain, gateway_name=gateway_name))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def gateway_ca_secret(request, cluster, blame, client_ca):
    """CA secret in the gateway namespace for EnvoyFilter volume mount"""
    secret = Secret.create_instance(cluster, blame("gw-ca"), stringData={"ca.crt": client_ca.certificate})
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret


@pytest.fixture(scope="module")
def envoy_filter(request, cluster, blame, gateway, gateway_ca_secret, module_label):
    """EnvoyFilter that enables client certificate validation on the gateway"""
    ca_mount_path = "/etc/istio/client-ca-certs"
    gateway.deployment.add_volume(SecretVolume(secret_name=gateway_ca_secret.name(), name="client-ca"))
    gateway.deployment.add_mount(VolumeMount(mountPath=ca_mount_path, name="client-ca"))

    envoy_filter = EnvoyFilter.create_instance(cluster, blame("ef"), gateway=gateway, labels={"app": module_label})
    envoy_filter.add_client_cert_validation(port_number=TLSGatewayListener.port, ca_cert_path=f"{ca_mount_path}/ca.crt")
    request.addfinalizer(envoy_filter.delete)
    envoy_filter.commit()
    return envoy_filter


@pytest.fixture(scope="module", autouse=True)
def commit(request, tls_policy, authorization, envoy_filter):  # pylint: disable=unused-argument
    """Commits TLSPolicy and AuthPolicy after EnvoyFilter is set up"""
    for component in [tls_policy, authorization]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()


def test_valid_cert(hostname, server_ca, valid_cert):
    """Test that a request with a valid client certificate succeeds"""
    with hostname.client(verify=server_ca, cert=valid_cert) as client:
        response = client.get("/get")
        assert response.status_code == 200


def test_no_cert(hostname, server_ca):
    """
    Test that a request without a client certificate is rejected at the gateway level (L4),
    where certificate validation is happening due to the EnvoyFilter configuration
    """
    with hostname.client(verify=server_ca) as client:
        response = client.get("/get")
        assert response.has_cert_required_error()


def test_invalid_cert(hostname, server_ca, invalid_cert):
    """
    Test that a request with a certificate signed by an untrusted CA is rejected at the gateway level (L4),
    where certificate validation is happening due to the EnvoyFilter configuration
    """
    with hostname.client(verify=server_ca, cert=invalid_cert) as client:
        response = client.get("/get")
        assert response.has_unknown_ca_error()
