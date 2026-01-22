"""Conftest for all tests requiring direct access to Authorino Operator"""

import pytest

from testsuite.gateway.envoy import Envoy
from testsuite.kuadrant.authorino import AuthorinoCR, Authorino


@pytest.fixture(scope="module")
def gateway(request, authorino, cluster, blame, label, testconfig) -> Envoy:
    """Deploys Envoy that wires up the Backend behind the reverse-proxy and Authorino instance"""
    gw = Envoy(  # pylint: disable=abstract-class-instantiated
        cluster,
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
def authorino(cluster, blame, request, testconfig, label, authorino_parameters) -> Authorino:
    """Module scoped Authorino instance, with specific parameters"""
    authorino_config = testconfig["service_protection"]["authorino"]
    if not authorino_config["deploy"]:
        return pytest.skip("Can't change parameters of already deployed Authorino")

    labels = authorino_parameters.setdefault("label_selectors", [])
    labels.append(f"testRun={label}")

    authorino_parameters.setdefault("name", blame("authorino"))

    authorino = AuthorinoCR.create_instance(
        cluster,
        image=authorino_config.get("image"),
        log_level=authorino_config.get("log_level"),
        **authorino_parameters,
    )
    request.addfinalizer(authorino.delete)
    authorino.commit()
    authorino.wait_for_ready()
    return authorino
