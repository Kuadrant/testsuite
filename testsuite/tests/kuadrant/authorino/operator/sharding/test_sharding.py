"""Test for authorino sharding"""
import pytest


@pytest.fixture(scope="module")
def authorino_parameters(authorino_parameters):
    """Setup sharding for authorino"""
    authorino_parameters["label_selectors"] = ["sharding=A"]
    yield authorino_parameters


def test_sharding(authorization, authorino, envoy):
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
    envoy1 = envoy(authorino)
    envoy2 = envoy(authorino)
    authorization(envoy1.hostname, "A")
    authorization(envoy2.hostname, "B")

    response = envoy1.client().get("/get")
    assert response.status_code == 200

    response = envoy2.client().get("/get")
    assert response.status_code == 404
