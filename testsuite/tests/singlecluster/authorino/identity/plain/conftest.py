"""Conftest for JWT plain identity tests"""

import pytest


@pytest.fixture(scope="module")
def realm_role(keycloak, blame):
    """Creates new realm role"""
    return keycloak.realm.create_realm_role(blame("role"))


@pytest.fixture(scope="module")
def user_with_role(keycloak, realm_role, blame):
    """Creates new user and adds him into realm_role"""
    username = blame("someuser")
    password = blame("password")
    user = keycloak.realm.create_user(username, password)
    user.assign_realm_role(realm_role)
    return user
