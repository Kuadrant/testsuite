"""Conftest for MGC tests"""

import pytest
from openshift_client import selector
from weakget import weakget

from testsuite.gateway import CustomReference, GatewayRoute, Exposer
from testsuite.policy.dns_policy import DNSPolicy
from testsuite.gateway.gateway_api.gateway import MGCGateway
from testsuite.gateway.gateway_api.hostname import DNSPolicyExposer
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.policy.tls_policy import TLSPolicy
from testsuite.utils import generate_tail


@pytest.fixture(scope="session")
def spokes(testconfig):
    """Returns Map of spokes names and their respective clients"""
    spokes = weakget(testconfig)["control_plane"]["spokes"] % {}
    assert len(spokes) > 0, "No spokes configured"
    return spokes


@pytest.fixture(scope="session")
def hub_openshift(testconfig):
    """Openshift client for a Hub cluster"""
    client = testconfig["control_plane"]["hub"]
    if not client.connected:
        pytest.fail("You are not logged into Openshift or the namespace doesn't exist")
    return client


@pytest.fixture(scope="module")
def hub_gateway(request, hub_openshift, blame, base_domain, module_label) -> MGCGateway:
    """Creates and returns configured and ready Hub Gateway"""
    hub_gateway = MGCGateway.create_instance(
        openshift=hub_openshift,
        name=blame("mgc-gateway"),
        gateway_class="kuadrant-multi-cluster-gateway-instance-per-cluster",
        hostname=f"*.{base_domain}",
        tls=True,
        placement="http-gateway",
        labels={"app": module_label},
    )
    request.addfinalizer(hub_gateway.delete_tls_secret)  # pylint: disable=no-member
    request.addfinalizer(hub_gateway.delete)
    hub_gateway.commit()
    # we cannot wait here because of referencing not yet existent tls secret which would be provided later by tlspolicy
    # upstream_gateway.wait_for_ready()

    return hub_gateway


@pytest.fixture(scope="session")
def cluster_issuer():
    """Reference to cluster self-signed certificate issuer"""
    return CustomReference(
        group="cert-manager.io",
        kind="ClusterIssuer",
        name="selfsigned-cluster-issuer",
    )


@pytest.fixture(scope="module")
def route(request, gateway, blame, hostname, backend, module_label) -> GatewayRoute:
    """Route object"""
    route = HTTPRoute.create_instance(gateway.openshift, blame("route"), gateway, {"app": module_label})
    route.add_hostname(hostname.hostname)
    route.add_backend(backend)
    request.addfinalizer(route.delete)
    route.commit()
    return route


@pytest.fixture(scope="module")
def exposer(base_domain, hub_gateway) -> Exposer:
    """DNSPolicyExposer setup with expected TLS certificate"""
    return DNSPolicyExposer(base_domain, tls_cert=hub_gateway.get_tls_cert())


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def gateway(hub_gateway, spokes, hub_policies_commit):
    """Downstream gateway, e.g. gateway on a spoke cluster"""
    # wait for upstream gateway here to be able to get spoke gateways
    hub_gateway.wait_for_ready()
    gw = hub_gateway.get_spoke_gateway(spokes)
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def openshift(gateway):
    """OpenShift client for the primary namespace"""
    return gateway.openshift


@pytest.fixture(scope="module", params=["aws-mz", "gcp-mz"])
def base_domain(request, hub_openshift):
    """Returns preconfigured base domain"""
    mz_name = request.param

    zone = selector(f"managedzone/{mz_name}", static_context=hub_openshift.context).object()
    return f"{generate_tail()}.{zone.model['spec']['domainName']}"


@pytest.fixture(scope="module")
def dns_policy(blame, hub_gateway, module_label):
    """DNSPolicy fixture"""
    policy = DNSPolicy.create_instance(hub_gateway.openshift, blame("dns"), hub_gateway, labels={"app": module_label})
    return policy


@pytest.fixture(scope="module")
def tls_policy(blame, hub_gateway, module_label, cluster_issuer):
    """TLSPolicy fixture"""
    policy = TLSPolicy.create_instance(
        hub_gateway.openshift,
        blame("tls"),
        parent=hub_gateway,
        issuer=cluster_issuer,
        labels={"app": module_label},
    )
    return policy


@pytest.fixture(scope="module")
def hub_policies_commit(request, hub_gateway, dns_policy, tls_policy):
    """Commits all important stuff before tests"""
    for component in [dns_policy, tls_policy]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()
