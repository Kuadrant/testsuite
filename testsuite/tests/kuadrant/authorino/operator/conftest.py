"""Conftest for all tests requiring custom deployment of Authorino"""
import pytest
from weakget import weakget

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.openshift.objects.authorino import AuthorinoCR


@pytest.fixture(scope="module")
def authorization(authorization, rhsso_service_info):
    """Add RHSSO identity to AuthConfig"""
    authorization.add_oidc_identity("rhsso", rhsso_service_info.issuer_url())
    return authorization


@pytest.fixture(scope="module")
def auth(rhsso_service_info):
    """Returns RHSSO authentication object for HTTPX"""
    return HttpxOidcClientAuth(rhsso_service_info.client, "authorization",
                               rhsso_service_info.username, rhsso_service_info.password)


@pytest.fixture(scope="module")
def authorino_parameters():
    """Optional parameters for Authorino creation, passed to the __init__"""
    return {}


@pytest.fixture(scope="module")
def authorino(openshift, blame, request, testconfig, authorino_parameters) -> AuthorinoCR:
    """Custom deployed Authorino instance"""
    if not testconfig["authorino"]["deploy"]:
        return pytest.skip("Operator tests don't work with already deployed Authorino")

    authorino = AuthorinoCR.create_instance(openshift,
                                            blame("authorino"),
                                            image=weakget(testconfig)["authorino"]["image"] % None,
                                            **authorino_parameters)
    request.addfinalizer(lambda: authorino.delete(ignore_not_found=True))
    authorino.commit()
    authorino.wait_for_ready()
    return authorino
