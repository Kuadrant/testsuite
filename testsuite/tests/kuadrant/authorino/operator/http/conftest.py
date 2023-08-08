"""Conftest for all tests requiring custom deployment of Authorino"""
import pytest

from testsuite.objects import Property, Value
from testsuite.httpx import HttpxBackoffClient
from testsuite.openshift.objects.auth_config import AuthConfig


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def authorization(authorization, wildcard_domain, openshift, module_label) -> AuthConfig:
    """In case of Authorino, AuthConfig used for authorization"""
    authorization.remove_all_hosts()
    authorization.add_host(wildcard_domain)
    authorization.responses.json(
        "another-json-returned-in-a-header", [Property("propX", Value("valueX"))], wrapper_key="x-ext-auth-other-json"
    )
    return authorization


@pytest.fixture(scope="module")
def client(authorization, authorino_route):
    """Returns httpx client to be used for requests, it also commits AuthConfig"""
    client = HttpxBackoffClient(base_url=f"http://{authorino_route.model.spec.host}", verify=False)
    yield client
    client.close()


@pytest.fixture(scope="module")
def authorino_route(authorino, blame, openshift):
    """Add route for authorino http port to be able to access it."""
    route = openshift.routes.expose(blame("route"), f"{authorino.name()}-authorino-authorization", port="http")
    yield route
    route.delete()
