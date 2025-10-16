"""Conftest for multicluster tests using a shared database storage."""

from importlib import resources
import time

import httpx
from dynaconf import ValidationError
import httpx
import pytest

from testsuite.certificates import Certificate
from testsuite.kubernetes.secret import Secret
from testsuite.httpx import KuadrantClient


# @pytest.fixture(scope="session", params=["redis", "dragonfly", "valkey"])
@pytest.fixture(scope="session", params=["redis"])
def storage_service(testconfig, request, skip_or_fail):
    """Returns the multicluster-accessible URL of the storage tool service."""
    try:
        testconfig.validators.validate(only=f"{request.param}.url")
        return testconfig[request.param]["url"]
    except ValidationError as exc:
        return skip_or_fail(f"{request.param} is missing: {exc}")


@pytest.fixture(scope="session")
def storage_secret1(testconfig, cluster, blame, request, storage_service):
    """Creates the Secret for Limitador in the first cluster."""
    system_project = cluster.change_project(testconfig["service_protection"]["system_project"])

    secret = Secret.create_instance(system_project, blame("storage-secret"), {"URL": storage_service})
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret


@pytest.fixture(scope="session")
def storage_secret2(testconfig, cluster2, blame, request, storage_service):
    """Creates the Secret for Limitador in the second cluster."""
    system_project = cluster2.change_project(testconfig["service_protection"]["system_project"])

    secret = Secret.create_instance(system_project, blame("storage-secret-cl2"), {"URL": storage_service})
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret


# @pytest.fixture(scope="module")
# def client1(hostname):
#     """Simple client 1"""
#     root_cert = resources.files("testsuite.resources").joinpath("kuadrant_qe_ca.crt").read_text()
#     client = hostname.client(verify=Certificate(certificate=root_cert, chain=root_cert, key=""))
#     yield client
#     client.close()
#
#
# @pytest.fixture(scope="module")
# def client2(hostname):
#     """Simple client 2"""
#     root_cert = resources.files("testsuite.resources").joinpath("kuadrant_qe_ca.crt").read_text()
#     client = hostname.client(verify=Certificate(certificate=root_cert, chain=root_cert, key=""))
#     yield client
#     client.close()

@pytest.fixture(scope="module")
def client1(gateway, hostname):
    """Client targeting the gateway in the first cluster directly via its IP address."""
    ip_address = gateway.external_ip()
    # Handle case where external_ip returns IP:port format
    if ":" in ip_address:
        ip_address = ip_address.split(":")[0]
    
    client = KuadrantClient(
        verify=False,
        base_url=f"http://{ip_address}",
        headers={"Host": hostname.hostname}
    )
    yield client
    client.close()


@pytest.fixture(scope="module")
def client2(gateway2, hostname):
    """Client targeting the gateway in the second cluster directly via its IP address."""
    ip_address = gateway2.external_ip()
    # Handle case where external_ip returns IP:port format
    if ":" in ip_address:
        ip_address = ip_address.split(":")[0]
    
    client = KuadrantClient(
        verify=False,
        base_url=f"http://{ip_address}",
        headers={"Host": hostname.hostname}
    )
    yield client
    client.close()

@pytest.fixture(scope="module")
def warm_up_clients(client1, client2):
    """
    Ensures that both clients can successfully connect to their gateways
    before the actual test logic runs. This prevents flaky tests due to network readiness.
    """
    for client_name, client in [("client1", client1), ("client2", client2)]:
        for i in range(10):
            try:
                response = client.get("/get", timeout=5)
                if response.status_code == 200:
                    break
            except httpx.ConnectError as e:
                print(f"Warm-up for {client_name} attempt {i+1} failed: {e}")

            if i == 9:
                pytest.fail(f"{client_name} warm-up failed after multiple retries.")

            time.sleep(5)
