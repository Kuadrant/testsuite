"""Conftest for Authorino tests"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.authorino import AuthorinoCR, PreexistingAuthorino
from testsuite.kuadrant.policy.authorization.auth_config import AuthConfig


@pytest.fixture(scope="session")
def authorino(kuadrant, cluster, blame, request, testconfig, label):
    """Authorino instance"""
    if kuadrant:
        return kuadrant.authorino

    authorino_config = testconfig["service_protection"]["authorino"]
    if not authorino_config["deploy"]:
        return PreexistingAuthorino(
            authorino_config["auth_url"],
            authorino_config["oidc_url"],
            authorino_config["metrics_service_name"],
        )

    authorino = AuthorinoCR.create_instance(
        cluster,
        image=authorino_config.get("image"),
        log_level=authorino_config.get("log_level"),
        name=blame("authorino"),
        label_selectors=[f"testRun={label}"],
    )
    request.addfinalizer(authorino.delete)
    authorino.commit()
    authorino.wait_for_ready()
    return authorino


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider, route, authorization_name, cluster, label) -> AuthConfig:
    """In case of Authorino, AuthConfig used for authorization"""
    if authorization is None:
        authorization = AuthConfig.create_instance(cluster, authorization_name, route, labels={"testRun": label})
    authorization.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module", autouse=True)
def commit(request, route, authorization):  # pylint: disable=unused-argument
    """Commits all important stuff before tests"""
    request.addfinalizer(authorization.delete)
    authorization.commit()
    authorization.wait_for_ready()
