"""Conftest for Multicluster tests"""

from importlib import resources
from typing import TypeVar

import pytest
from openshift_client import selector, OpenShiftPythonException

from testsuite.backend.httpbin import Httpbin
from testsuite.certificates import Certificate
from testsuite.gateway import Exposer, Gateway, CustomReference, Hostname
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.gateway.gateway_api.hostname import DNSPolicyExposer
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kubernetes.client import KubernetesClient
from testsuite.policy import Policy
from testsuite.policy.dns_policy import DNSPolicy
from testsuite.policy.tls_policy import TLSPolicy


AnyPolicy = TypeVar("AnyPolicy", bound=Policy)


def generate_policies(clusters: list[KubernetesClient], policy: AnyPolicy) -> dict[KubernetesClient, AnyPolicy]:
    """Copy policies for each cluster"""
    return {cluster: policy.__class__(policy.as_dict(), context=cluster.context) for cluster in clusters}


@pytest.fixture(scope="module")
def cluster_issuer(testconfig, cluster, skip_or_fail):
    """Reference to cluster Let's Encrypt certificate issuer"""
    testconfig.validators.validate(only="letsencrypt")
    name = testconfig["letsencrypt"]["issuer"]["name"]
    kind = testconfig["letsencrypt"]["issuer"]["kind"]
    try:
        selector(f"{kind}/{name}", static_context=cluster.context).object()
    except OpenShiftPythonException as exc:
        skip_or_fail(f"{kind}/{name} is not present on the cluster: {exc}")
    return CustomReference(
        group="cert-manager.io",
        kind=kind,
        name=name,
    )


@pytest.fixture(scope="session")
def clusters(testconfig, cluster, skip_or_fail) -> list[KubernetesClient]:
    """Returns list of all clusters on which to run Multicluster tests"""
    additional_clusters = testconfig["control_plane"]["additional_clusters"]
    if len(additional_clusters) == 0:
        skip_or_fail("Only one cluster was provided for multi-cluster tests")
    return [
        cluster,
        *(cluster.change_project(testconfig["service_protection"]["project"]) for cluster in additional_clusters),
    ]


@pytest.fixture(scope="session")
def backends(request, clusters, blame, label, testconfig) -> dict[KubernetesClient, Httpbin]:
    """Deploys Backend to each Kubernetes cluster"""
    backends = {}
    name = blame("httpbin")
    image = testconfig["httpbin"]["image"]
    for cluster in clusters:
        httpbin = Httpbin(cluster, name, label, image)
        request.addfinalizer(httpbin.delete)
        httpbin.commit()
        backends[cluster] = httpbin
    return backends


@pytest.fixture(scope="module")
def gateways(request, clusters, blame, label, wildcard_domain) -> dict[KubernetesClient, Gateway]:
    """Deploys Gateway to each Kubernetes cluster"""
    gateways = {}
    name = blame("gw")
    for cluster in clusters:
        gw = KuadrantGateway.create_instance(cluster, name, wildcard_domain, {"app": label}, tls=True)
        request.addfinalizer(gw.delete)
        gw.commit()
        gateways[cluster] = gw
    for gateway in gateways.values():
        gateway.wait_for_ready()
    return gateways


@pytest.fixture(scope="module")
def routes(request, gateways, blame, hostname, backends, module_label) -> dict[KubernetesClient, HTTPRoute]:
    """Deploys HttpRoute to each Kubernetes cluster"""
    routes = {}
    name = blame("route")
    for client, gateway in gateways.items():
        route = HTTPRoute.create_instance(gateway.cluster, name, gateway, {"app": module_label})
        route.add_hostname(hostname.hostname)
        route.add_backend(backends[client])
        request.addfinalizer(route.delete)
        route.commit()
        routes[client] = route
    return routes


@pytest.fixture(scope="module")
def hostname(gateways, cluster, exposer, blame) -> Hostname:
    """Exposed Hostname object"""
    hostname = exposer.expose_hostname(blame("hostname"), gateways[cluster])
    return hostname


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


@pytest.fixture(scope="module")
def dns_policy(blame, cluster, gateways, module_label):
    """DNSPolicy fixture"""
    policy = DNSPolicy.create_instance(cluster, blame("dns"), gateways[cluster], labels={"app": module_label})
    return policy


@pytest.fixture(scope="module")
def tls_policy(blame, cluster, gateways, module_label, cluster_issuer):
    """TLSPolicy fixture"""
    policy = TLSPolicy.create_instance(
        cluster,
        blame("tls"),
        parent=gateways[cluster],
        issuer=cluster_issuer,
        labels={"app": module_label},
    )
    return policy


@pytest.fixture(scope="module")
def dns_policies(clusters, dns_policy) -> dict[KubernetesClient, DNSPolicy]:
    """Creates DNSPolicy for each Kubernetes cluster"""
    return generate_policies(clusters, dns_policy)


@pytest.fixture(scope="module")
def tls_policies(clusters, tls_policy) -> dict[KubernetesClient, TLSPolicy]:
    """Creates TLSPolicy for each Kubernetes cluster"""
    return generate_policies(clusters, tls_policy)


@pytest.fixture(scope="module")
def client(hostname, gateways):  # pylint: disable=unused-argument
    """Returns httpx client to be used for requests"""
    root_cert = resources.files("testsuite.resources").joinpath("letsencrypt-stg-root-x1.pem").read_text()
    client = hostname.client(verify=Certificate(certificate=root_cert, chain=root_cert, key=""))
    yield client
    client.close()


@pytest.fixture(scope="module", autouse=True)
def commit(request, routes, dns_policies, tls_policies):  # pylint: disable=unused-argument
    """Commits all policies before tests"""
    components = [*dns_policies.values(), *tls_policies.values()]
    for component in components:
        request.addfinalizer(component.delete)
        component.commit()
    for component in components:
        component.wait_for_ready()
