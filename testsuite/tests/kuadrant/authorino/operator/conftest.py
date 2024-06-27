"""Conftest for all tests requiring direct access to Authorino Operator"""

import pytest

from testsuite.gateway.envoy import Envoy
from testsuite.openshift.authorino import AuthorinoCR, Authorino


@pytest.fixture(scope="module")
def gateway(request, authorino, openshift, blame, label, testconfig) -> Envoy:
    """Deploys Envoy that wires up the Backend behind the reverse-proxy and Authorino instance"""
    gw = Envoy(
        openshift,
        blame("gw"),
        authorino,
        testconfig["service_protection"]["envoy"]["image"],
        labels={"app": label},
    )
    request.addfinalizer(gw.delete)
    gw.commit()
    gw.wait_for_ready()
    return gw


@pytest.fixture(scope="module")
def authorino_parameters():
    """Optional parameters for Authorino creation, passed to the __init__"""
    return {}


@pytest.fixture(scope="module")
def authorino(openshift, blame, request, testconfig, label, authorino_parameters) -> Authorino:
    """Module scoped Authorino instance, with specific parameters"""
    authorino_config = testconfig["service_protection"]["authorino"]

    authorino = AuthorinoCR.create_instance(
        openshift,
        image=authorino_config.get("image"),
        log_level=authorino_config.get("log_level"),
        name=blame("authorino"),
        label_selectors=[f"testRun={label}"],
        **authorino_parameters,
    )
    request.addfinalizer(authorino.delete)
    authorino.commit()
    authorino.wait_for_ready()
    return authorino
