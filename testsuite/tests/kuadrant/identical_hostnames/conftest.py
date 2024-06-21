"""Conftest for "identical hostname" tests"""

import pytest

from testsuite.gateway import GatewayRoute
from testsuite.gateway.gateway_api.route import HTTPRoute


@pytest.fixture(scope="module", autouse=True)
def route2(request, gateway, blame, hostname, backend, module_label) -> GatewayRoute:
    """HTTPRoute object serving as a 2nd route declaring identical hostname but different path"""
    route = HTTPRoute.create_instance(gateway.openshift, blame("route"), gateway, {"app": module_label})
    route.add_hostname(hostname.hostname)
    route.add_backend(backend, "/anything/")
    request.addfinalizer(route.delete)
    route.commit()
    return route


@pytest.fixture(scope="module")
def authorization_name2(blame):
    """Name of the 2nd Authorization resource"""
    return blame("authz2")
