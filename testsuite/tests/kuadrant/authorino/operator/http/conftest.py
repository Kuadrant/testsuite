"""Conftest for all tests requiring custom deployment of Authorino"""
import pytest

from testsuite.objects import Authorization
from testsuite.httpx import HttpxBackoffClient


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def authorization(authorization, wildcard_domain, blame, openshift, rhsso_service_info, module_label) -> Authorization:
    """In case of Authorino, AuthConfig used for authorization"""
    authorization.remove_all_hosts()
    authorization.add_host(wildcard_domain)
    resp = {'name': 'another-json-returned-in-a-header',
            'wrapperKey': 'x-ext-auth-other-json',
            'json': {'properties': [
                {'name': 'propX', 'value': 'valueX'}
            ]}}
    authorization.add_response(response=resp)
    return authorization


@pytest.fixture(scope="module")
def client_http_auth(authorization, authorino_route):
    """Returns httpx client to be used for requests, it also commits AuthConfig"""
    client = HttpxBackoffClient(base_url=f"http://{authorino_route.model.spec.host}", verify=False)
    yield client
    client.close()


@pytest.fixture(scope="module")
def authorino_route(authorino, blame, openshift):
    """Add route for authorino http port to be able to access it."""
    name = f"route-{authorino.name()}"
    route = openshift.routes.expose(name, f"{authorino.name()}-authorino-authorization",
                                    port='http')
    yield route
    route.delete()
