"""Conftest for Authorino tests"""
import pytest
from weakget import weakget

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.openshift.objects.auth_config import AuthConfig
from testsuite.objects import Authorino, Authorization, PreexistingAuthorino
from testsuite.openshift.objects.authorino import AuthorinoCR


@pytest.fixture(scope="module")
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
def authorization(authorization, authorino, envoy, blame, openshift, label, rhsso_service_info) -> Authorization:
    """In case of Authorino, AuthConfig used for authorization"""
    if authorization is None:
        authorization = AuthConfig.create_instance(openshift, blame("ac"), envoy.hostname, labels={"testRun": label})
    authorization.add_oidc_identity("rhsso", rhsso_service_info.issuer_url())
    return authorization


@pytest.fixture(scope="module")
def auth(rhsso_service_info):
    """Returns RHSSO authentication object for HTTPX"""
    return HttpxOidcClientAuth(rhsso_service_info.client, "authorization",
                               rhsso_service_info.username, rhsso_service_info.password)


@pytest.fixture(scope="module")
def client(authorization, envoy):
    """Returns httpx client to be used for requests, it also commits AuthConfig"""
    client = envoy.client()
    yield client
    client.close()
