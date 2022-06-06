"""Conftest for Authorino tests"""
import pytest

from testsuite.openshift.httpbin import EnvoyHttpbin
from testsuite.openshift.objects.auth_config import AuthConfig
from testsuite.openshift.objects.authorino import Authorino


@pytest.fixture(scope="session")
def authorino(openshift, blame, request):
    """Authorino instance"""
    authorino = Authorino.create_instance(openshift, blame("authorino"))
    request.addfinalizer(authorino.delete)
    authorino.commit()
    authorino.wait_for_ready()
    return authorino


@pytest.fixture(scope="module")
def backend(request, authorino, openshift, blame):
    """Backend with proxy"""
    httpbin = EnvoyHttpbin(openshift, authorino, blame("backend"), "backend")
    request.addfinalizer(httpbin.destroy)
    httpbin.create()
    return httpbin


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def auth_config(authorino, backend, blame, openshift):
    """AuthConfig used for authorization"""
    return AuthConfig.create_instance(openshift, blame("ac"), backend.hostname)


@pytest.fixture(scope="module")
def client(auth_config, backend):
    """Returns httpx client to be used for requests, it also commit AuthConfig"""
    auth_config.commit()
    client = backend.client
    yield client
    client.close()
    auth_config.delete()
