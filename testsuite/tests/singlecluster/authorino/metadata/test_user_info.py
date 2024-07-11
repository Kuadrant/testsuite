"""
Tests for external auth metadata. Online fetching of (OIDC) UserInfo data, associated with an OIDC identity source:
https://github.com/Kuadrant/authorino/blob/main/docs/features.md#oidc-userinfo-metadatauserinfo
"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy.authorization import Pattern

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def user2(keycloak, blame):
    """Second User which has incorrect email"""
    return keycloak.realm.create_user("user2", "password", email=f"{blame('test')}@test.com")


@pytest.fixture(scope="module")
def authorization(authorization, keycloak):
    """
    Adds auth metadata OIDC UserInfo which fetches OIDC UserInfo in request-time.
    Adds a simple rule that accepts only when fetched UserInfo contains the email address of the default Keycloak user.
    """
    authorization.metadata.add_user_info("user-info", "default")
    authorization.authorization.add_auth_rules(
        "rule", [Pattern("auth.metadata.user-info.email", "eq", keycloak.user.properties["email"])]
    )
    return authorization


def test_correct_auth(client, auth):
    """Tests auth when UserInfo email matches the email address"""
    response = client.get("get", auth=auth)
    assert response.status_code == 200


def test_incorrect_auth(client, keycloak, user2):
    """Updates Keycloak user email address and tests incorrect auth"""
    auth = HttpxOidcClientAuth.from_user(keycloak.get_token, user2, "authorization")
    response = client.get("get", auth=auth)
    assert response.status_code == 403
