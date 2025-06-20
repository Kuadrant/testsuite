"""Conftest for JWT plain identity tests"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.gateway.envoy.route import EnvoyVirtualRoute


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


@pytest.fixture(scope="module")
def auth2(user_with_role, keycloak):
    """Creates user with role and returns its authentication object for HTTPX"""
    return HttpxOidcClientAuth.from_user(keycloak.get_token, user_with_role, "authorization")


@pytest.fixture(scope="module")
def route(request, gateway, blame, hostname, backend):
    """Route object"""
    route = EnvoyVirtualRoute.create_instance(gateway.cluster, blame("route"), gateway)
    route.add_hostname(hostname.hostname)
    route.add_backend(backend)
    request.addfinalizer(route.delete)
    gateway.wait_for_ready()
    route.commit()
    return route
