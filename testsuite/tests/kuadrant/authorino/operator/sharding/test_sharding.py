"""Test for authorino sharding"""

import pytest


@pytest.fixture(scope="module")
def authorino_parameters(authorino_parameters):
    """Setup sharding for authorino"""
    authorino_parameters["label_selectors"] = ["sharding=A"]
    yield authorino_parameters


def test_sharding(setup_authorization, setup_gateway, setup_route, authorino, exposer, blame):
    """
    Setup:
        - Create Authorino that watch only AuthConfigs with label `sharding=A`
    Test:
        - Create AuthConfig with `sharding=A` label
        - Create AuthConfig with `sharding=B` label
        - Send a request to the first AuthConfig
        - Assert that the response status code is 200
        - Send a request to the second AuthConfig
        - Assert that the response status code is 404
    """
    gw = setup_gateway(authorino)
    hostname = exposer.expose_hostname(blame("first"), gw)
    route = setup_route(hostname.hostname, gw)
    setup_authorization(route, sharding_label="A")

    gw2 = setup_gateway(authorino)
    hostname2 = exposer.expose_hostname(blame("second"), gw2)
    route2 = setup_route(hostname2.hostname, gw2)
    setup_authorization(route2, sharding_label="B")

    response = hostname.client().get("/get")
    assert response.status_code == 200

    response = hostname2.client().get("/get")
    assert response.status_code == 404
