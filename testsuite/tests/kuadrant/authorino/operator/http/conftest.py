"""Conftest for all tests requiring custom deployment of Authorino"""
import pytest

from testsuite.objects import Value, JsonResponse
from testsuite.httpx import HttpxBackoffClient
from testsuite.openshift.objects.auth_config import AuthConfig
from testsuite.openshift.objects.route import OpenshiftRoute


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def authorization(authorization, wildcard_domain, openshift, module_label) -> AuthConfig:
    """In case of Authorino, AuthConfig used for authorization"""
    authorization.remove_all_hosts()
    authorization.add_host(wildcard_domain)
    authorization.responses.add_success_header("x-ext-auth-other-json", JsonResponse({"propX": Value("valueX")}))
    return authorization


@pytest.fixture(scope="module")
def client(authorization, authorino_route):
    """Returns httpx client to be used for requests, it also commits AuthConfig"""
    client = HttpxBackoffClient(base_url=f"http://{authorino_route.model.spec.host}", verify=False)
    yield client
    client.close()


@pytest.fixture(scope="module")
def authorino_route(request, authorino, blame, openshift):
    """Add route for authorino http port to be able to access it."""
    route = OpenshiftRoute.create_instance(
        openshift, blame("route"), f"{authorino.name()}-authorino-authorization", target_port="http"
    )
    request.addfinalizer(route.delete)
    route.commit()
    return route
