"""Test for authorino sharding"""
import pytest

from testsuite.openshift.httpbin import Envoy
from testsuite.openshift.objects.auth_config import AuthConfig


@pytest.fixture(scope="module")
def authorino_parameters(authorino_parameters):
    """Setup TLS for authorino"""
    authorino_parameters["label_selectors"] = ["sharding=true"]
    yield authorino_parameters


@pytest.fixture(scope="module")
def envoy(request, authorino, openshift, blame, backend, module_label):
    """Envoy"""

    def _envoy():
        envoy = Envoy(openshift, authorino, blame("envoy"), module_label, backend.url)
        request.addfinalizer(envoy.delete)
        envoy.commit()
        return envoy

    return _envoy


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def authorization(request, authorino, blame, openshift, module_label):
    """In case of Authorino, AuthConfig used for authorization"""

    def _authorization(envoy, sharding):
        auth = AuthConfig.create_instance(openshift, blame("ac"), envoy.hostname,
                                          labels={"testRun": module_label, "sharding": sharding})
        request.addfinalizer(auth.delete)
        auth.commit()
        return auth

    return _authorization


@pytest.fixture(scope="module", autouse=True)
def commit():
    """Ensure no default resources are created"""
    return


def test_sharding(authorization, envoy):
    """
    Setup:
        - Create Authorino that watch only AuthConfigs with label `sharding=true`
    Test:
        - Create AuthConfig with `sharding=true` label
        - Create AuthConfig with `sharding=false` label
        - Send a request to the first AuthConfig
        - Assert that the response status code is 200
        - Send a request to the second AuthConfig
        - Assert that the response status code is 404
    """
    envoy1 = envoy()
    envoy2 = envoy()
    authorization(envoy1, "true")
    authorization(envoy2, "false")

    response = envoy1.client().get("/get")
    assert response.status_code == 200

    response = envoy2.client().get("/get")
    assert response.status_code == 404
