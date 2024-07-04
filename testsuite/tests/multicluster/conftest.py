"""Conftest for Multicluster tests"""

import time
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
from testsuite.openshift.client import OpenShiftClient
from testsuite.policy import Policy
from testsuite.policy.dns_policy import DNSPolicy
from testsuite.policy.tls_policy import TLSPolicy


AnyPolicy = TypeVar("AnyPolicy", bound=Policy)


def generate_policies(clusters: list[OpenShiftClient], policy: AnyPolicy) -> dict[OpenShiftClient, AnyPolicy]:
    """Copy policies for each cluster"""
    return {cluster: policy.__class__(policy.as_dict(), context=cluster.context) for cluster in clusters}


@pytest.fixture(scope="module")
def cluster_issuer(testconfig, hub_openshift, skip_or_fail):
    """Reference to cluster Let's Encrypt certificate issuer"""
    testconfig.validators.validate(only="letsencrypt")
    name = testconfig["letsencrypt"]["issuer"]["name"]
    kind = testconfig["letsencrypt"]["issuer"]["kind"]
    try:
        selector(f"{kind}/{name}", static_context=hub_openshift.context).object()
    except OpenShiftPythonException as exc:
        skip_or_fail(f"{kind}/{name} is not present on the cluster: {exc}")
    return CustomReference(
        group="cert-manager.io",
        kind=kind,
        name=name,
    )


@pytest.fixture(scope="session")
def openshifts(testconfig, hub_openshift, skip_or_fail) -> list[OpenShiftClient]:
    """Returns list of all OpenShifts on which to run Multicluster"""
    additional_clusters = testconfig["control_plane"]["additional_clusters"]
    if len(additional_clusters) == 0:
        skip_or_fail("Only one cluster was provided for multi-cluster tests")
    return [
        hub_openshift,
        *(cluster.change_project(testconfig["service_protection"]["project"]) for cluster in additional_clusters),
    ]


@pytest.fixture(scope="session")
def backends(request, openshifts, blame, label) -> dict[OpenShiftClient, Httpbin]:
    """Deploys Backend to each Openshift server"""
    backends = {}
    name = blame("httpbin")
    for openshift in openshifts:
        httpbin = Httpbin(openshift, name, label)
        request.addfinalizer(httpbin.delete)
        httpbin.commit()
        backends[openshift] = httpbin
    return backends


@pytest.fixture(scope="module")
def gateways(request, openshifts, blame, label, wildcard_domain) -> dict[OpenShiftClient, Gateway]:
    """Deploys Gateway to each Openshift server"""
    gateways = {}
    name = blame("gw")
    for openshift in openshifts:
        gw = KuadrantGateway.create_instance(openshift, name, wildcard_domain, {"app": label}, tls=True)
        request.addfinalizer(gw.delete)
        gw.commit()
        gateways[openshift] = gw
    for gateway in gateways.values():
        gateway.wait_for_ready()
    return gateways


@pytest.fixture(scope="module")
def routes(request, gateways, blame, hostname, backends, module_label) -> dict[OpenShiftClient, HTTPRoute]:
    """Deploys HttpRoute to each Openshift server"""
    routes = {}
    name = blame("route")
    for client, gateway in gateways.items():
        route = HTTPRoute.create_instance(gateway.openshift, name, gateway, {"app": module_label})
        route.add_hostname(hostname.hostname)
        route.add_backend(backends[client])
        request.addfinalizer(route.delete)
        route.commit()
        routes[client] = route
    return routes


@pytest.fixture(scope="module")
def hostname(gateways, hub_openshift, exposer, blame) -> Hostname:
    """Exposed Hostname object"""
    hostname = exposer.expose_hostname(blame("hostname"), gateways[hub_openshift])
    return hostname


@pytest.fixture(scope="module")
def exposer(request, hub_openshift) -> Exposer:
    """Expose using DNSPolicy"""
    exposer = DNSPolicyExposer(hub_openshift)
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
    Wildcard domain of openshift cluster
    """
    return f"*.{base_domain}"


@pytest.fixture(scope="module")
def dns_policy(blame, hub_openshift, gateways, module_label):
    """DNSPolicy fixture"""
    policy = DNSPolicy.create_instance(
        hub_openshift, blame("dns"), gateways[hub_openshift], labels={"app": module_label}
    )
    return policy


@pytest.fixture(scope="module")
def tls_policy(blame, hub_openshift, gateways, module_label, cluster_issuer):
    """TLSPolicy fixture"""
    policy = TLSPolicy.create_instance(
        hub_openshift,
        blame("tls"),
        parent=gateways[hub_openshift],
        issuer=cluster_issuer,
        labels={"app": module_label},
    )
    return policy


@pytest.fixture(scope="module")
def dns_policies(openshifts, dns_policy) -> dict[OpenShiftClient, DNSPolicy]:
    """Creates DNSPolicy for each Openshift server"""
    return generate_policies(openshifts, dns_policy)


@pytest.fixture(scope="module")
def tls_policies(openshifts, tls_policy) -> dict[OpenShiftClient, TLSPolicy]:
    """Creates TLSPolicy for each Openshift server"""
    return generate_policies(openshifts, tls_policy)


@pytest.fixture(scope="module")
def client(hostname, gateways):  # pylint: disable=unused-argument
    """Returns httpx client to be used for requests"""
    time.sleep(180)  # it takes a bit for the lets encrypt secret to be actually created
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