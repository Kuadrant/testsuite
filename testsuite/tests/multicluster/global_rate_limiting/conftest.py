"""Conftest for multicluster tests using a shared database storage."""

import pytest
from dynaconf import ValidationError
from openshift_client import selector

from testsuite.kuadrant import KuadrantCR
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy
from testsuite.kubernetes.secret import Secret
from testsuite.httpx import KuadrantClient
from testsuite.gateway import GatewayListener
from testsuite.gateway.gateway_api.gateway import KuadrantGateway


@pytest.fixture(scope="session")
def kuadrant1(testconfig, cluster):
    """Returns the existing Kuadrant instance from the first cluster."""
    project = testconfig["service_protection"]["system_project"]
    kuadrant_cluster = cluster.change_project(project)

    with kuadrant_cluster.context:
        kuadrant = selector("kuadrant").object(cls=KuadrantCR)
    return kuadrant


@pytest.fixture(scope="session")
def kuadrant2(testconfig, cluster2):
    """Returns the existing Kuadrant instance from the second cluster."""
    project = testconfig["service_protection"]["system_project"]
    kuadrant_cluster = cluster2.change_project(project)

    with kuadrant_cluster.context:
        kuadrant = selector("kuadrant").object(cls=KuadrantCR)
    return kuadrant


@pytest.fixture(scope="session")
def limitador1(kuadrant1):
    """Returns the default LimitadorCR from the first cluster."""
    return kuadrant1.limitador


@pytest.fixture(scope="session")
def limitador2(kuadrant2):
    """Returns the default LimitadorCR from the second cluster."""
    return kuadrant2.limitador


@pytest.fixture(scope="session", params=["redis", "dragonfly", "valkey"])
def storage_service(testconfig, request, skip_or_fail):
    """Returns the multicluster-accessible URL of the storage tool service."""
    try:
        testconfig.validators.validate(only=f"{request.param}.url")
        return testconfig[request.param]["url"]
    except ValidationError as exc:
        return skip_or_fail(f"{request.param} is missing: {exc}")


@pytest.fixture(scope="module")
def storage_secret1(testconfig, cluster, blame, request, storage_service):
    """Creates the Secret for Limitador in the first cluster."""
    system_project = cluster.change_project(testconfig["service_protection"]["system_project"])

    secret = Secret.create_instance(system_project, blame("storage-secret"), {"URL": storage_service})
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret


@pytest.fixture(scope="module")
def storage_secret2(testconfig, cluster2, blame, request, storage_service):
    """Creates the Secret for Limitador in the second cluster."""
    system_project = cluster2.change_project(testconfig["service_protection"]["system_project"])

    secret = Secret.create_instance(system_project, blame("storage-secret-cl2"), {"URL": storage_service})
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret


@pytest.fixture(scope="module")
def gateway(cluster, blame, label, wildcard_domain):
    """Gateway to first Kubernetes cluster with HTTP listener"""
    name = blame("gw")
    gw = KuadrantGateway.create_instance(cluster, name, {"app": label})
    gw.add_listener(GatewayListener(port=80, protocol="HTTP", hostname=wildcard_domain))
    return gw


@pytest.fixture(scope="module")
def gateway2(cluster2, blame, label, wildcard_domain):
    """Gateway to second Kubernetes cluster with HTTP listener"""
    name = blame("gw")
    gw = KuadrantGateway.create_instance(cluster2, name, {"app": label})
    gw.add_listener(GatewayListener(port=80, protocol="HTTP", hostname=wildcard_domain))
    return gw


@pytest.fixture(scope="module")
def client1(gateway, hostname):
    """Client targeting the gateway in the first cluster directly via its IP address."""
    ip_address = gateway.external_ip()
    client = KuadrantClient(verify=False, base_url=f"http://{ip_address}", headers={"Host": hostname.hostname})
    yield client
    client.close()


@pytest.fixture(scope="module")
def client2(gateway2, hostname):
    """Client targeting the gateway in the second cluster directly via its IP address."""
    ip_address = gateway2.external_ip()
    client = KuadrantClient(verify=False, base_url=f"http://{ip_address}", headers={"Host": hostname.hostname})
    yield client
    client.close()


@pytest.fixture(scope="module")
def configured_limitador1(limitador1, request, storage1):
    """Applies `storage1` config to the first Limitador and waits for it to be ready."""
    request.addfinalizer(limitador1.reset_storage)
    limitador1.set_storage(storage1)
    limitador1.wait_for_ready()
    return limitador1


@pytest.fixture(scope="module")
def configured_limitador2(limitador2, request, storage2):
    """Applies `storage2` config to the second Limitador and waits for it to be ready."""
    request.addfinalizer(limitador2.reset_storage)
    limitador2.set_storage(storage2)
    limitador2.wait_for_ready()
    return limitador2


@pytest.fixture(scope="function")
def rate_limit_policy1(routes, limit, cluster, rate_limit_name):
    """Creates a RateLimitPolicy object for the first cluster."""
    route = routes[0]
    rlp = RateLimitPolicy.create_instance(cluster, rate_limit_name, route)
    rlp.add_limit("global", [limit])
    return rlp


@pytest.fixture(scope="function")
def rate_limit_policy2(routes, limit, cluster2, rate_limit_name):
    """Creates a RateLimitPolicy object for the second cluster."""
    route = routes[1]
    rlp = RateLimitPolicy.create_instance(cluster2, rate_limit_name, route)
    rlp.add_limit("global", [limit])
    return rlp


@pytest.fixture(scope="function")
def rate_limit_name(blame):
    """Returns a unique, shared name for the RateLimitPolicy."""
    return blame("rlp")


@pytest.fixture(scope="function", autouse=True)
def commit_policies(
    request,
    rate_limit_policy1,
    rate_limit_policy2,
    configured_limitador1,  # pylint: disable=unused-argument
    configured_limitador2,  # pylint: disable=unused-argument
):
    """Commits both RateLimitPolicies before the test runs and registers their cleanup."""
    request.addfinalizer(rate_limit_policy1.delete)
    request.addfinalizer(rate_limit_policy2.delete)
    rate_limit_policy1.commit()
    rate_limit_policy2.commit()
    rate_limit_policy1.wait_for_ready()
    rate_limit_policy2.wait_for_ready()
