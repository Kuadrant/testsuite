"""Conftest for Authorino tests"""
import pytest

from testsuite.openshift.objects.auth_config import AuthConfig
from testsuite.objects import Authorino, Authorization, PreexistingAuthorino
from testsuite.openshift.objects.authorino import AuthorinoCR


@pytest.fixture(scope="session")
def authorino(authorino, openshift, blame, request, testconfig) -> Authorino:
    """Authorino instance"""
    if authorino:
        return authorino

    if not testconfig["authorino"]["deploy"]:
        return PreexistingAuthorino(testconfig["authorino"]["url"])

    authorino = AuthorinoCR.create_instance(openshift, blame("authorino"))
    request.addfinalizer(lambda: authorino.delete(ignore_not_found=True))
    authorino.commit()
    authorino.wait_for_ready()
    return authorino


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def authorization(authorization, authorino, backend, blame, openshift) -> Authorization:
    """In case of Authorino, AuthConfig used for authorization"""
    if authorization:
        return authorization

    return AuthConfig.create_instance(openshift, blame("ac"), backend.hostname)


@pytest.fixture(scope="module")
def client(authorization, backend):
    """Returns httpx client to be used for requests, it also commit AuthConfig"""
    authorization.commit()
    client = backend.client
    yield client
    client.close()
    authorization.delete()
