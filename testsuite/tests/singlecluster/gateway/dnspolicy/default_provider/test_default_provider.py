"""Test default DNS provider secret"""

import pytest

import openshift_client as oc

from testsuite.gateway import GatewayListener
from testsuite.kubernetes.secret import Secret
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.kuadrant.policy.dns import DNSPolicy

pytestmark = [pytest.mark.dnspolicy, pytest.mark.disruptive]


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, wildcard_domain, module_label):
    """Returns gateway without tls"""
    gw = KuadrantGateway.create_instance(
        cluster,
        blame("gw"),
        {"app": module_label},
    )
    gw.add_listener(GatewayListener(hostname=wildcard_domain))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def dns_provider_secret(request, dns_provider_secret, cluster, blame, module_label):
    """Get existing DNS provider secret and create a copy with default-provider label"""
    provider_secret = oc.selector(f"secret/{dns_provider_secret}", static_context=cluster.context).object(cls=Secret)
    default_secret = Secret.create_instance(
        cluster,
        blame("dflt-dns"),
        data=provider_secret.model.data,
        secret_type=provider_secret.model.type,
        labels={"kuadrant.io/default-provider": "true", "app": module_label},
    )
    request.addfinalizer(default_secret.delete)
    default_secret.commit()


@pytest.fixture(scope="module")
def dns_policy(blame, gateway, module_label):
    """Return DNSPolicy without proivderRefs configured"""
    return DNSPolicy.create_instance(gateway.cluster, blame("dns"), gateway, labels={"app": module_label})


@pytest.fixture(scope="module", autouse=True)
def commit(request, dns_provider_secret, dns_policy):  # pylint: disable=unused-argument
    """Commits all important stuff before tests"""
    request.addfinalizer(dns_policy.delete)
    dns_policy.commit()
    dns_policy.wait_for_ready()


def test_default_dns_provider(gateway, dns_policy, client):
    """Test if default DNS provider secret is picked up and used"""
    assert gateway.refresh().is_affected_by(dns_policy)
    response = client.get("/get")
    assert response.status_code == 200
