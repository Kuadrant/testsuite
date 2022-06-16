"""Conftest for Authorino tests"""
import pytest

from testsuite.openshift.objects.auth_config import AuthConfig
from testsuite.openshift.objects.authorino import Authorino


@pytest.fixture(scope="session")
def authorino(authorino, openshift, blame, request):
    """Authorino instance"""
    if authorino:
        return authorino

    authorino = Authorino.create_instance(openshift, blame("authorino"))
    request.addfinalizer(lambda: authorino.delete(ignore_not_found=True))
    authorino.commit()
    authorino.wait_for_ready()
    return authorino


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def authorization(authorization, authorino, backend, blame, openshift):
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
