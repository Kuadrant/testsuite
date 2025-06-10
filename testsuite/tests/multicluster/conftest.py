"""Conftest for Multicluster tests"""

from importlib import resources

import pytest

from testsuite.backend.httpbin import Httpbin
from testsuite.certificates import Certificate
from testsuite.gateway import Exposer, Hostname
from testsuite.gateway import TLSGatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.hostname import DNSPolicyExposer
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy.dns import DNSPolicy
from testsuite.kuadrant.policy.tls import TLSPolicy


@pytest.fixture(scope="session")
def cluster2(testconfig):
    """Kubernetes client for the primary namespace"""
    if not testconfig["control_plane"]["cluster2"]:
        pytest.skip("Second cluster is not configured properly")

    project = testconfig["service_protection"]["project"]
    client = testconfig["control_plane"]["cluster2"].change_project(project)
    if not client.connected:
        pytest.fail(f"You are not logged into the second cluster or the {project} namespace doesn't exist")
    return client


@pytest.fixture(scope="module")
def hostname(gateway, exposer, blame) -> Hostname:
    """Exposed Hostname object"""
    return exposer.expose_hostname(blame("hostname"), gateway)


@pytest.fixture(scope="module")
def exposer(request, cluster) -> Exposer:
    """Expose using DNSPolicy"""
    exposer = DNSPolicyExposer(cluster)
    request.addfinalizer(exposer.delete)
    exposer.commit()
    return exposer


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


@pytest.fixture(scope="session")
def backends(request, cluster, cluster2, blame, label, testconfig) -> list[Httpbin]:
    """Deploys Backend to each Kubernetes cluster"""
    backends = []
    name = blame("httpbin")
    image = testconfig["httpbin"]["image"]
    for client in [cluster, cluster2]:
        httpbin = Httpbin(client, name, label, image)
        request.addfinalizer(httpbin.delete)
        httpbin.commit()
        backends.append(httpbin)
    return backends


@pytest.fixture(scope="module")
def routes(request, gateway, gateway2, blame, hostname, backends, module_label) -> list[HTTPRoute]:
    """Deploys HttpRoute for each gateway"""
    routes = []
    name = blame("route")
    for i, gateway_ in enumerate([gateway, gateway2]):
        route = HTTPRoute.create_instance(gateway_.cluster, name, gateway_, {"app": module_label})
        route.add_hostname(hostname.hostname)
        route.add_backend(backends[i])
        request.addfinalizer(route.delete)
        route.commit()
        routes.append(route)
    return routes


@pytest.fixture(scope="module")
def gateway(request, cluster, blame, label, wildcard_domain):
    """Deploys Gateway to first Kubernetes cluster"""
    name = blame("gw")
    gw = KuadrantGateway.create_instance(cluster, name, {"app": label})
    gw.add_listener(TLSGatewayListener(hostname=wildcard_domain, gateway_name=name))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def gateway2(request, cluster2, blame, label, wildcard_domain):
    """Deploys Gateway to second Kubernetes cluster"""
    name = blame("gw")
    gw = KuadrantGateway.create_instance(cluster2, name, {"app": label})
    gw.add_listener(TLSGatewayListener(hostname=wildcard_domain, gateway_name=name))
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def dns_policy(blame, cluster, gateway, dns_provider_secret, module_label):
    """DNSPolicy for the first cluster"""
    return DNSPolicy.create_instance(cluster, blame("dns"), gateway, dns_provider_secret, labels={"app": module_label})


@pytest.fixture(scope="module")
def dns_policy2(blame, cluster2, gateway2, dns_provider_secret, module_label):
    """DNSPolicy for the second cluster"""
    return DNSPolicy.create_instance(
        cluster2, blame("dns"), gateway2, dns_provider_secret, labels={"app": module_label}
    )


@pytest.fixture(scope="module")
def tls_policy(blame, cluster, gateway, module_label, cluster_issuer):
    """TLSPolicy for the first cluster"""
    return TLSPolicy.create_instance(
        cluster,
        blame("tls"),
        parent=gateway,
        issuer=cluster_issuer,
        labels={"app": module_label},
    )


@pytest.fixture(scope="module")
def tls_policy2(blame, cluster2, gateway2, module_label, cluster_issuer):
    """TLSPolicy for the second cluster"""
    return TLSPolicy.create_instance(
        cluster2,
        blame("tls"),
        parent=gateway2,
        issuer=cluster_issuer,
        labels={"app": module_label},
    )


@pytest.fixture(scope="module")
def client(hostname, gateway, gateway2):  # pylint: disable=unused-argument
    """Returns httpx client to be used for requests"""
    root_cert = resources.files("testsuite.resources").joinpath("kuadrant_qe_ca.crt").read_text()
    client = hostname.client(verify=Certificate(certificate=root_cert, chain=root_cert, key=""))
    yield client
    client.close()


@pytest.fixture(scope="module", autouse=True)
def commit(request, routes, dns_policy, dns_policy2, tls_policy, tls_policy2):  # pylint: disable=unused-argument
    """Commits all policies before tests"""
    components = [dns_policy, dns_policy2, tls_policy, tls_policy2]
    for component in components:
        request.addfinalizer(component.delete)
        component.commit()
    for component in components:
        component.wait_for_ready()
