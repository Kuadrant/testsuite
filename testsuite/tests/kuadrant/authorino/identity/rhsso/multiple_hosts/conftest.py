"""Conftest for multiple hosts tests"""
import pytest


@pytest.fixture(scope="module")
def hostname(envoy):
    """Original hostname"""
    return envoy.hostname


@pytest.fixture(scope="module")
def second_hostname(envoy, blame):
    """Second valid hostname"""
    service_name = envoy.route.model.spec.to.name
    route = envoy.openshift.do_action("expose", "service", f"--name={blame('second')}", "-o", "json",
                                      service_name, parse_output=True)
    yield route.model.spec.host
    with envoy.openshift.context:
        route.delete(ignore_not_found=True)
