"""Test DNSPolicy behavior when invalid credentials are provided"""

import pytest

from testsuite.kubernetes.secret import Secret
from testsuite.kuadrant.policy import has_condition
from testsuite.kuadrant.policy.dns import has_record_condition
from testsuite.gateway.gateway_api.gateway import KuadrantGateway, GatewayListener

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy]


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, wildcard_domain, module_label):
    """Create gateway without TLS enabled"""
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": module_label})
    gw.add_listener(GatewayListener(hostname=wildcard_domain, name="api"))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def dns_provider_secret(request, cluster, module_label, blame):
    """Create AWS provider secret with invalid credentials"""
    creds = {
        "AWS_ACCESS_KEY_ID": "ABCDEFGHIJKL",
        "AWS_SECRET_ACCESS_KEY": "abcdefg12345+",
    }

    secret = Secret.create_instance(
        cluster, blame("creds"), creds, secret_type="kuadrant.io/aws", labels={"app": module_label}
    )
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret.name()


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, dns_policy):  # pylint: disable=unused-argument
    """Commits dnspolicy without waiting for it to be ready"""
    request.addfinalizer(dns_policy.delete)
    dns_policy.commit()


def test_invalid_credentials(dns_policy):
    """Verify that DNSPolicy is not ready or enforced when invalid credentials are provided"""
    assert dns_policy.wait_until(
        has_condition("Enforced", "False")
    ), f"DNSPolicy did not reach expected status, instead it was: {dns_policy.model.status.conditions}"
    assert dns_policy.wait_until(
        has_record_condition("Ready", "False", "DNSProviderError", "InvalidClientTokenId")
    ), f"DNSPolicy did not reach expected record status, instead it was: {dns_policy.model.status.recordConditions}"
