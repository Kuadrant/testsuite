"""
This module contains the most basic happy path test for both DNSPolicy and TLSPolicy
for a cluster with Let's Encrypt Issuer

Prerequisites:
* cert-manager Operator installed
* Let's Encrypt Issuer object configured on the cluster matching the template:
apiVersion: cert-manager.io/v1
kind: ClusterIssuer | Issuer
metadata:
  name: letsencrypt-staging-issuer
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
import ssl
from importlib import resources

import pytest
from openshift_client import selector
from openshift_client.model import OpenShiftPythonException

from testsuite.gateway import CustomReference
from testsuite.httpx import create_tmp_file

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy, pytest.mark.tlspolicy]


@pytest.fixture(scope="module")
def cluster_issuer(testconfig, cluster):
    """Reference to cluster Let's Encrypt certificate issuer"""
    testconfig.validators.validate(only="letsencrypt")
    name = testconfig["letsencrypt"]["issuer"]["name"]
    kind = testconfig["letsencrypt"]["issuer"]["kind"]
    try:
        selector(f"{kind}/{name}", static_context=cluster.context).object()
    except OpenShiftPythonException as exc:
        pytest.skip(f"{name} {kind} is not present on the cluster: {exc}")
    return CustomReference(
        group="cert-manager.io",
        kind=kind,
        name=name,
    )


@pytest.fixture(scope="module")
def client(hostname, gateway):
    """Returns httpx client to be used for requests, it also commits AuthConfig"""
    root_cert = resources.files("testsuite.resources").joinpath("letsencrypt-stg-root-x1.pem").read_text()
    old_cert = gateway.get_tls_cert(hostname.hostname)
    cert = dataclasses.replace(old_cert, chain=old_cert.certificate + root_cert)

    # Injecting the certificate as a string literal has been deprecated, hence we write to a local file, that during
    # the teardown of the fixture will be removed.
    verify_file = create_tmp_file(cert.chain)
    client = hostname.client(verify=ssl.create_default_context(cafile=verify_file.name))
    yield client
    client.close()


def test_letsencrypt(client, auth):
    """
    Tests whether the backend, exposed using the HTTPRoute and Gateway, was exposed correctly,
    having a tls secured endpoint with a hostname managed by MGC
    """

    result = client.get("/get", auth=auth)
    assert not result.has_dns_error()
    assert not result.has_cert_verify_error()
    assert result.status_code == 200
