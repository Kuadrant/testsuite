"""Conftest for gateway tests"""

import pytest

from testsuite.gateway import Exposer
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.hostname import DNSPolicyExposer
from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.kuadrant.policy.tls import TLSPolicy


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, wildcard_domain, module_label):
    """Returns ready gateway"""
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), wildcard_domain, {"app": module_label}, tls=True)
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    # pylint: disable=unused-argument
    """Create AuthPolicy attached to gateway"""
    authorization.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns Authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def rate_limit():
    """
    For these tests don't create any RateLimitPolicy
    Parent rate_limit fixture calls some fixtures that result in extra Gateway created as a side effect
    """
    return None


@pytest.fixture(scope="module")
def exposer(request, cluster) -> Exposer:
    """DNSPolicyExposer setup with expected TLS certificate"""
    exposer = DNSPolicyExposer(cluster)
    request.addfinalizer(exposer.delete)
    exposer.commit()
    return exposer


@pytest.fixture(scope="module")
def dns_policy(blame, gateway, module_label, dns_provider_secret):
    """DNSPolicy fixture"""
    policy = DNSPolicy.create_instance(
        gateway.cluster, blame("dns"), gateway, dns_provider_secret, labels={"app": module_label}
    )
    return policy


@pytest.fixture(scope="module")
def tls_policy(blame, gateway, module_label, cluster_issuer):
    """TLSPolicy fixture"""
    policy = TLSPolicy.create_instance(
        gateway.cluster,
        blame("tls"),
        parent=gateway,
        issuer=cluster_issuer,
        labels={"app": module_label},
    )
    return policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, rate_limit, dns_policy, tls_policy):
    """Commits all important stuff before tests"""
    for component in [dns_policy, tls_policy, authorization, rate_limit]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()
            component.wait_for_ready()


@pytest.fixture(scope="module")
def base_domain(exposer):
    """Returns preconfigured base domain"""
    return exposer.base_domain


@pytest.fixture(scope="module")
def wildcard_domain(base_domain):
    """
    Wildcard domain for the exposer
    """
    return f"*.{base_domain}"
