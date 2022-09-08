"""Basic test of role based authentication"""
import pytest
from testsuite.httpx.auth import HttpxOidcClientAuth


@pytest.fixture(scope="function")
def user_with_role(rhsso, realm_role, blame):
    """Creates new user and adds him into realm_role"""
    username = blame("someuser")
    password = blame("password")
    user_id = rhsso.realm.create_user(username, password)
    rhsso.realm.assign_realm_role(realm_role, user_id)
    return {"id": user_id, "username": username, "password": password}


@pytest.fixture(scope="module")
def realm_role(rhsso, blame):
    """Creates new realm role"""
    return rhsso.realm.create_realm_role(blame("role"))


@pytest.fixture(scope="module")
def authorization(authorization, realm_role, blame):
    """Adds rule, that requires user to be part of realm_role to be allowed access."""
    authorization.add_role_rule(blame("rule"), realm_role["name"], "^/get")
    return authorization


def test_user_with_role(client, user_with_role, rhsso):
    """Test request when user does have required role using new user with assigned role"""
    auth = HttpxOidcClientAuth(rhsso.get_token(user_with_role["username"], user_with_role["password"]),
                               "authorization")
    response = client.get("/get", auth=auth)
    assert response.status_code == 200


def test_user_without_role(client, auth):
    """Test request when user doesn't have required role using default user"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 403
