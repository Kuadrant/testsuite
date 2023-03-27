"""Conftest for Authorino tests"""
import pytest
from weakget import weakget

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.objects import Authorino, Authorization, PreexistingAuthorino
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects.api_key import APIKey
from testsuite.openshift.objects.auth_config import AuthConfig
from testsuite.openshift.objects.authorino import AuthorinoCR


@pytest.fixture(scope="module")
def authorino_parameters():
    """Optional parameters for Authorino creation, passed to the __init__"""
    return {}


@pytest.fixture(scope="module")
def authorino(authorino, openshift, blame, request, testconfig, module_label, authorino_parameters) -> Authorino:
    """Authorino instance"""
    if authorino:
        return authorino

    if not testconfig["authorino"]["deploy"]:
        if len(authorino_parameters) > 0:
            return pytest.skip("Can't change parameters of already deployed Authorino")
        return PreexistingAuthorino(testconfig["authorino"]["url"])

    labels = authorino_parameters.setdefault("label_selectors", [])
    labels.append(f"testRun={module_label}")

    authorino_parameters.setdefault("name", blame("authorino"))

    authorino = AuthorinoCR.create_instance(
        openshift,
        image=weakget(testconfig)["authorino"]["image"] % None,
        log_level=weakget(testconfig)["authorino"]["log_level"] % None,
        **authorino_parameters,
    )
    request.addfinalizer(lambda: authorino.delete(ignore_not_found=True))
    authorino.commit()
    authorino.wait_for_ready()
    return authorino


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def authorization(
    authorization, oidc_provider, authorino, envoy, authorization_name, openshift, module_label
) -> Authorization:
    """In case of Authorino, AuthConfig used for authorization"""
    if authorization is None:
        authorization = AuthConfig.create_instance(
            openshift, authorization_name, envoy.route, labels={"testRun": module_label}
        )
    authorization.identity.oidc("rhsso", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns RHSSO authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def create_api_key(blame, request, openshift):
    """Creates API key Secret"""

    def _create_secret(name, label_selector, api_key, ocp: OpenShiftClient = openshift):
        secret_name = blame(name)
        secret = APIKey.create_instance(ocp, secret_name, label_selector, api_key)
        request.addfinalizer(lambda: secret.delete(ignore_not_found=True))
        secret.commit()
        return secret

    return _create_secret


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization):
    """Commits all important stuff before tests"""
    request.addfinalizer(authorization.delete)
    authorization.commit()
