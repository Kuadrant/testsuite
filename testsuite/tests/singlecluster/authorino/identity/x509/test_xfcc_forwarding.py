"""Tests for x509 client certificate authentication using XFCC forwarding.
Tier 3 from RFC 0015 - https://github.com/Kuadrant/architecture/blob/main/rfcs/0015-x509-client-cert-authpolicy.md

L7-only validation where the gateway does NOT validate client certificates at the TLS level.
Instead, the client sends the certificate in the X-Forwarded-Client-Cert header, and the gateway
is configured to forward it as-is. Authorino is the sole certificate validator via x509 identity.
"""

import pytest

from testsuite.gateway import GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from .conftest import XFCC_HEADER_NAME

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only, pytest.mark.data_plane]


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, wildcard_domain, module_label):
    """Gateway with XFCC forwarding via gatewayTopology annotation (no TLS client validation)"""
    gw = KuadrantGateway.create_instance(
        cluster,
        blame("gw"),
        labels={"app": module_label},
        annotations={
            "proxy.istio.io/config": '{"gatewayTopology": {"forwardClientCertDetails": "ALWAYS_FORWARD_ONLY"}}'
        },
    )
    gw.add_listener(GatewayListener(hostname=wildcard_domain))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


def test_valid_cert(client, valid_cert):
    """Test that a request with a valid certificate in XFCC header succeeds"""
    response = client.get("/get", headers={XFCC_HEADER_NAME: valid_cert.xfcc_header})
    assert response.status_code == 200


def test_no_header(client):
    """Test that a request without XFCC header is rejected by Authorino.
    The gateway does not reject it at TLS level - it passes through to Authorino for validation."""
    response = client.get("/get")
    assert not response.has_cert_required_error()
    assert response.status_code == 401


def test_invalid_cert(client, invalid_cert):
    """Test that a certificate signed by a different CA is rejected by Authorino.
    The gateway does not reject it at TLS level - it passes through to Authorino for validation."""
    response = client.get("/get", headers={XFCC_HEADER_NAME: invalid_cert.xfcc_header})
    assert not response.has_unknown_ca_error()
    assert response.status_code == 401
