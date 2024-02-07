"""Basic test of role based authentication"""

import pytest
from testsuite.httpx.auth import HttpxOidcClientAuth

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="function")
def user_with_role(rhsso, realm_role, blame):
    """Creates new user and adds him into realm_role"""
    username = blame("someuser")
    password = blame("password")
    user = rhsso.realm.create_user(username, password)
    user.assign_realm_role(realm_role)
    return user


@pytest.fixture(scope="module")
def authorization(authorization, realm_role, blame):
    """Adds rule, that requires user to be part of realm_role to be allowed access."""
    authorization.authorization.add_role_rule(blame("rule"), realm_role["name"], "^/get")
    return authorization


def test_user_with_role(client, user_with_role, rhsso):
    """Test request when user does have required role using new user with assigned role"""
    auth = HttpxOidcClientAuth.from_user(rhsso.get_token, user_with_role, "authorization")
    response = client.get("/get", auth=auth)
    assert response.status_code == 200


def test_user_without_role(client, auth):
    """Test request when user doesn't have required role using default user"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 403
