"""Conftest for Authorino tests"""
import pytest
from weakget import weakget

from testsuite.openshift.objects.auth_config import AuthConfig
from testsuite.objects import Authorino, Authorization, PreexistingAuthorino
from testsuite.openshift.objects.authorino import AuthorinoCR


@pytest.fixture(scope="session")
def authorino(authorino, openshift, blame, request, testconfig, label) -> Authorino:
    """Authorino instance"""
    if authorino:
        return authorino

    if not testconfig["authorino"]["deploy"]:
        return PreexistingAuthorino(testconfig["authorino"]["url"])

    authorino = AuthorinoCR.create_instance(openshift,
                                            blame("authorino"),
                                            image=weakget(testconfig)["authorino"]["image"] % None,
                                            label_selectors=[f"testRun={label}"])
    request.addfinalizer(lambda: authorino.delete(ignore_not_found=True))
    authorino.commit()
    authorino.wait_for_ready()
    return authorino


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def authorization(authorization, authorino, envoy, blame, openshift, label) -> Authorization:
    """In case of Authorino, AuthConfig used for authorization"""
    if authorization:
        return authorization

    return AuthConfig.create_instance(openshift, blame("ac"), envoy.hostname, labels={"testRun": label})


@pytest.fixture(scope="module")
def client(authorization, envoy):
    """Returns httpx client to be used for requests, it also commit AuthConfig"""
    authorization.commit()
    client = envoy.client
    yield client
    client.close()
    authorization.delete()
