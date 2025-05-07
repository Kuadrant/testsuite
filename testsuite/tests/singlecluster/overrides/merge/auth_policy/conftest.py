"""Conftest for overrides merge strategy tests for AuthPolicies"""

import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth, HttpxOidcClientAuth
from testsuite.tests.singlecluster.overrides.merge.conftest import create_secret


@pytest.fixture(scope="module")
def user_label(blame):
    """Label for user related objects"""
    return blame("user")


@pytest.fixture(scope="module")
def admin_label(blame):
    """Label for admin related objects"""
    return blame("admin")


@pytest.fixture(scope="module")
def user_api_key(request, blame, user_label, cluster):
    """Creates API key Secret for user"""
    secret = create_secret(blame("api-key"), user_label, "api_key_value", cluster)
    request.addfinalizer(secret.delete)
    return secret


@pytest.fixture(scope="module")
def admin_api_key(request, blame, admin_label, cluster):
    """Creates API key Secret for admin"""
    secret = create_secret(
        blame("admin-api-key"), admin_label, "admin_api_key_value", cluster, {"kuadrant.io/groups": "admins"}
    )
    request.addfinalizer(secret.delete)
    return secret


@pytest.fixture(scope="module")
def user_auth(user_api_key):
    """Returns Authentication object for HTTPX"""
    return HeaderApiKeyAuth(user_api_key)


@pytest.fixture(scope="module")
def admin_auth(admin_api_key):
    """Valid API Key Auth"""
    return HeaderApiKeyAuth(admin_api_key)


@pytest.fixture()
def auth(oidc_provider):
    """Returns Authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")
