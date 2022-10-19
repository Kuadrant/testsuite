"""
Tests for external auth metadata. Online fetching of (OIDC) UserInfo data, associated with an OIDC identity source:
https://github.com/Kuadrant/authorino/blob/main/docs/features.md#oidc-userinfo-metadatauserinfo
"""
import pytest

from testsuite.openshift.objects.auth_config import Rule


@pytest.fixture(scope="module")
def authorization(authorization, rhsso):
    """
    Adds auth metadata OIDC UserInfo which fetches OIDC UserInfo in request-time.
    Adds a simple rule that accepts only when fetched UserInfo contains the email address of the default RHSSO user.
    """
    user = rhsso.client.admin.get_user(rhsso.user)
    authorization.add_user_info_metadata("user-info", "rhsso")
    authorization.add_auth_rule("rule", Rule("auth.metadata.user-info.email", "eq", user["email"]))
    return authorization


def test_correct_auth(client, auth):
    """Tests auth when UserInfo email matches the email address"""
    response = client.get("get", auth=auth)
    assert response.status_code == 200


def test_incorrect_auth(client, auth, rhsso):
    """Updates RHSSO user email address and tests incorrect auth"""
    rhsso.client.admin.update_user(rhsso.user, {"email": "updatedMail@anything.invalid"})
    response = client.get("get", auth=auth)
    assert response.status_code == 403
