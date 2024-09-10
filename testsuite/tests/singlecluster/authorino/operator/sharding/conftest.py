"""Conftest for authorino sharding tests"""

import pytest
from weakget import weakget

from testsuite.kuadrant.authorino import AuthorinoCR
from testsuite.kuadrant.policy.authorization import Value, JsonResponse
from testsuite.gateway.envoy import Envoy
from testsuite.kuadrant.policy.authorization.auth_config import AuthConfig
from testsuite.gateway.envoy.route import EnvoyVirtualRoute


@pytest.fixture(scope="module")
def setup_gateway(request, cluster, blame, testconfig, module_label):
    """Factory method for creating Gateways in the test run"""

    def _envoy(auth):
        gw = Envoy(
            cluster,
            blame("gw"),
            auth,
            testconfig["service_protection"]["envoy"]["image"],
            labels={"app": module_label},
        )
        request.addfinalizer(gw.delete)
        gw.commit()
        gw.wait_for_ready()
        return gw

    return _envoy


@pytest.fixture(scope="module")
def setup_route(request, blame, backend, module_label):
    """Factory method for creating Routes in the test run"""

    def _route(hostname, gateway):
        route = EnvoyVirtualRoute.create_instance(
            gateway.cluster, blame("route"), gateway, labels={"app": module_label}
        )
        route.add_hostname(hostname)
        route.add_backend(backend)
        request.addfinalizer(route.delete)
        route.commit()
        return route

    return _route


@pytest.fixture(scope="module")
def setup_authorino(cluster, blame, testconfig, module_label, request):
    """Authorino instance"""

    def _authorino(sharding_label):
        authorino = AuthorinoCR.create_instance(
            cluster,
            blame("authorino"),
            image=weakget(testconfig)["authorino"]["image"] % None,
            label_selectors=[f"sharding={sharding_label}", f"testRun={module_label}"],
        )
        request.addfinalizer(authorino.delete)
        authorino.commit()
        authorino.wait_for_ready()
        return authorino

    return _authorino


@pytest.fixture(scope="module")
def setup_authorization(request, blame, cluster, module_label):
    """Factory method for creating AuthConfigs in the test run"""

    def _authorization(route, sharding_label=None):
        auth = AuthConfig.create_instance(
            cluster,
            blame("ac"),
            route,
            labels={"testRun": module_label, "sharding": sharding_label},
        )
        auth.responses.add_success_header("header", JsonResponse({"anything": Value(sharding_label)}))
        request.addfinalizer(auth.delete)
        auth.commit()
        return auth

    return _authorization


@pytest.fixture(scope="module", autouse=True)
def commit():
    """Ensure no default resources are created"""
    return
