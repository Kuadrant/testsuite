"""Conftest for "identical hostname" tests"""

import pytest

from testsuite.gateway import GatewayRoute
from testsuite.gateway.gateway_api.route import HTTPRoute


@pytest.fixture(scope="module")
def route(route, backend):
    """Adding /anything/route1 prefix to the backend"""
    route.remove_all_backend()
    route.add_backend(backend, "/anything/route1")
    return route


@pytest.fixture(scope="module", autouse=True)
def route2(request, gateway, blame, hostname, backend, module_label) -> GatewayRoute:
    """HTTPRoute object serving as a 2nd route declaring identical hostname but different path"""
    route = HTTPRoute.create_instance(gateway.cluster, blame("route2"), gateway, {"app": module_label})
    route.add_hostname(hostname.hostname)
    route.add_backend(backend, "/anything/route2")
    request.addfinalizer(route.delete)
    route.commit()
    return route
