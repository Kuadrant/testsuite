"""
Conftest for changing targetRef field in policies
"""

import pytest

from testsuite.gateway import GatewayRoute, GatewayListener, Hostname, Exposer
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.hostname import DNSPolicyExposer
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy.dns import DNSPolicy


@pytest.fixture(scope="module")
def exposer2(request, cluster) -> Exposer:
    """Second DNSPolicyExposer setup for Gateway 2"""
    exposer = DNSPolicyExposer(cluster)
    request.addfinalizer(exposer.delete)
    exposer.commit()
    return exposer


@pytest.fixture(scope="module")
def base_domain2(exposer2):
    """Returns preconfigured base domain for the second Gateway"""
    return exposer2.base_domain


@pytest.fixture(scope="module")
def wildcard_domain2(base_domain2):
    """Wildcard domain for Gateway 2"""
    return f"*.{base_domain2}"


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, wildcard_domain, module_label):
    """Create and configure Gateway 1"""
    gw = KuadrantGateway.create_instance(cluster, blame("gw"), {"app": module_label})
    gw.add_listener(GatewayListener(hostname=wildcard_domain))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def gateway2(request, cluster, blame, wildcard_domain2, module_label):
    """Create and configure Gateway 2"""
    gw = KuadrantGateway.create_instance(cluster, blame("gw2"), {"app": module_label})
    gw.add_listener(GatewayListener(hostname=wildcard_domain2))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def hostname2(gateway2, exposer2, blame) -> Hostname:
    """Expose Hostname for Gateway 2"""
    hostname = exposer2.expose_hostname(blame("hostname2"), gateway2)
    return hostname


@pytest.fixture(scope="module")
def route2(request, gateway2, blame, hostname2, module_label, backend) -> GatewayRoute:
    """Create and configure Route 2"""
    route = HTTPRoute.create_instance(gateway2.cluster, blame("route2"), gateway2, {"app": module_label})
    route.add_hostname(hostname2.hostname)
    route.add_backend(backend)
    request.addfinalizer(route.delete)
    route.commit()
    route.wait_for_ready()
    return route


@pytest.fixture(scope="module")
def client2(route2, hostname2):  # pylint: disable=unused-argument
    """Returns httpx client for Gateway 2"""
    client = hostname2.client()
    yield client
    client.close()


@pytest.fixture(scope="module")
def dns_policy2(blame, gateway2, module_label, dns_provider_secret, request):
    """DNSPolicy fixture for Gateway 2"""
    policy = DNSPolicy.create_instance(
        gateway2.cluster, blame("dns2"), gateway2, dns_provider_secret, labels={"app": module_label}
    )
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()
    return policy


@pytest.fixture(scope="session")
def change_target_ref():
    """Function that changes targetRef of given policy"""

    def _change_targetref(policy, gateway):
        def _apply_target_ref(apiobj):
            apiobj.model.spec.targetRef = gateway.reference
            return True

        policy.modify_and_apply(_apply_target_ref)
        policy.wait_for_ready()

    return _change_targetref
