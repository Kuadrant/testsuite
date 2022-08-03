"""Test for authorino sharding"""
import pytest
from weakget import weakget

from testsuite.openshift.httpbin import Envoy
from testsuite.openshift.objects.auth_config import AuthConfig
from testsuite.openshift.objects.authorino import AuthorinoCR


@pytest.fixture(scope="session")
def authorino(openshift, blame, request, testconfig, label) -> AuthorinoCR:
    """Custom deployed Authorino instance"""
    if not testconfig["authorino"]["deploy"]:
        return pytest.skip("Operator tests don't work with already deployed Authorino")

    authorino = AuthorinoCR.create_instance(openshift,
                                            blame("authorino"),
                                            image=weakget(testconfig)["authorino"]["image"] % None,
                                            label_selectors=[f"testRun={label}", "sharding=true"])
    request.addfinalizer(lambda: authorino.delete(ignore_not_found=True))
    authorino.commit()
    authorino.wait_for_ready()
    return authorino


@pytest.fixture(scope="module")
def envoy(request, authorino, openshift, blame, backend, label):
    """Envoy"""

    def _envoy():
        envoy = Envoy(openshift, authorino, blame("envoy"), label, backend.url)
        request.addfinalizer(envoy.delete)
        envoy.commit()
        return envoy

    return _envoy


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def authorization(request, authorino, blame, openshift, label):
    """In case of Authorino, AuthConfig used for authorization"""

    def _authorization(envoy, sharding):
        auth = AuthConfig.create_instance(openshift, blame("ac"), envoy.hostname,
                                          labels={"testRun": label, "sharding": sharding})
        request.addfinalizer(auth.delete)
        auth.commit()
        return auth

    return _authorization


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

    response = envoy1.client.get("/get")
    assert response.status_code == 200

    response = envoy2.client.get("/get")
    assert response.status_code == 404
