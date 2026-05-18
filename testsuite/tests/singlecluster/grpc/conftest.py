"""Conftest for GRPCRoute tests, overrides backend/route/client for gRPC protocol"""

import pytest

from testsuite.backend.grpcbin import Grpcbin
from testsuite.grpc import GRPCClient
from testsuite.gateway.gateway_api.grpc_route import GRPCRoute


@pytest.fixture(scope="module")
def backend(request, cluster, blame, module_label, testconfig, cluster_issuer):
    """Deploys Grpcbin backend"""
    backend = Grpcbin(
        cluster, blame("grpcbin"), module_label, testconfig["grpcbin"]["image"], cluster_issuer=cluster_issuer
    )
    request.addfinalizer(backend.delete)
    backend.commit()
    return backend


@pytest.fixture(scope="module")
def route(request, gateway, blame, hostname, backend, module_label):
    """Creates GRPCRoute attached to the gateway"""
    route = GRPCRoute.create_instance(gateway.cluster, blame("route"), gateway, {"app": module_label})
    route.add_hostname(hostname.hostname)
    route.add_backend(backend)
    request.addfinalizer(route.delete)
    route.commit()
    route.wait_for_ready()
    return route


@pytest.fixture(scope="module")
def client(route, hostname, gateway):  # pylint: disable=unused-argument
    """Returns gRPC client"""
    client = GRPCClient(host=gateway.external_ip(), hostname=hostname.hostname)
    yield client
    client.close()
