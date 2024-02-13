"""
This module contains the most basic happy path test for both DNSPolicy and TLSPolicy
for a cluster with Let's Encrypt ClusterIssuer

Prerequisites:
* multi-cluster-gateways ns is created and set as openshift["project"]
* managedclustersetbinding is created in openshift["project"]
* gateway class "kuadrant-multi-cluster-gateway-instance-per-cluster" is created
* cert-manager Operator installed
* Let's Encrypt ClusterIssuer object configured on the cluster matching the template:
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    email: <email_address>
    preferredChain: ISRG Root X1
    privateKeySecretRef:
      name: letsencrypt-private-key
    server: 'https://acme-staging-v02.api.letsencrypt.org/directory'
    solvers:
      - dns01:
          route53:
            accessKeyID: <aws_key_id>
            hostedZoneID: <hosted_zone_id>
            region: <region_name>
            secretAccessKeySecretRef:
              key: awsSecretAccessKey
              name: aws-secret
"""

import dataclasses
from importlib import resources

import pytest
from openshift_client import selector
from openshift_client.model import OpenShiftPythonException

from testsuite.gateway import Exposer, CustomReference
from testsuite.gateway.gateway_api.hostname import DNSPolicyExposer

pytestmark = [pytest.mark.mgc]


@pytest.fixture(scope="module")
def cluster_issuer(hub_openshift):
    """Reference to cluster Let's Encrypt certificate issuer"""
    try:
        selector("clusterissuer/letsencrypt-staging", static_context=hub_openshift.context).object()
    except OpenShiftPythonException as exc:
        pytest.skip(f"letsencrypt-staging ClusterIssuer is not present on the cluster: {exc}")
    return CustomReference(
        group="cert-manager.io",
        kind="ClusterIssuer",
        name="letsencrypt-staging",
    )


@pytest.fixture(scope="module")
def exposer(base_domain, hub_gateway) -> Exposer:
    """DNSPolicyExposer setup with expected TLS certificate"""
    root_cert = resources.files("testsuite.resources").joinpath("letsencrypt-stg-root-x1.pem").read_text()
    old_cert = hub_gateway.get_tls_cert()
    return DNSPolicyExposer(base_domain, tls_cert=dataclasses.replace(old_cert, chain=old_cert.certificate + root_cert))


# Reduce scope of the base_domain fixture so the test only runs on aws-mz ManagedZone
@pytest.mark.parametrize("base_domain", ["aws-mz"], indirect=True)
def test_smoke_letsencrypt(client):
    """
    Tests whether the backend, exposed using the HTTPRoute and Gateway, was exposed correctly,
    having a tls secured endpoint with a hostname managed by MGC
    """

    result = client.get("/get")
    assert not result.has_dns_error()
    assert not result.has_cert_verify_error()
    assert result.status_code == 200
