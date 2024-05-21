"""Conftest for all tests requiring custom deployment of Authorino"""

import pytest

from testsuite.gateway.exposers import KindExposer
from testsuite.policy.authorization import Value, JsonResponse
from testsuite.httpx import KuadrantClient
from testsuite.policy.authorization.auth_config import AuthConfig
from testsuite.openshift.route import OpenshiftRoute


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def authorization(authorization, route, wildcard_domain, openshift, module_label) -> AuthConfig:
    """In case of Authorino, AuthConfig used for authorization"""
    authorization.remove_all_hosts()
    route.add_hostname(wildcard_domain)
    authorization.responses.add_success_header("x-ext-auth-other-json", JsonResponse({"propX": Value("valueX")}))
    return authorization


@pytest.fixture(scope="module")
def client(authorization, authorino_route):
    """Returns httpx client to be used for requests, it also commits AuthConfig"""
    client = KuadrantClient(base_url=f"http://{authorino_route.model.spec.host}", verify=False)
    yield client
    client.close()


@pytest.fixture(scope="module")
def authorino_route(request, exposer, authorino, blame, openshift):
    """Add route for authorino http port to be able to access it."""
    if isinstance(exposer, KindExposer):
        pytest.skip("raw_http is not available on Kind")

    route = OpenshiftRoute.create_instance(
        openshift, blame("route"), f"{authorino.name()}-authorino-authorization", target_port="http"
    )
    request.addfinalizer(route.delete)
    route.commit()
    return route
