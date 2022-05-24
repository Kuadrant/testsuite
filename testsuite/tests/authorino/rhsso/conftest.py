"""Conftest for authorino rhsso tests"""
import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth


@pytest.fixture(scope="module")
def auth_config(auth_config, rhsso_service_info):
    """Add RHSSO identity to AuthConfig"""
    auth_config.add_oidc_identity("rhsso", rhsso_service_info.issuer_url())
    return auth_config


@pytest.fixture(scope="module")
def auth(rhsso_service_info):
    return HttpxOidcClientAuth(rhsso_service_info.client, "authorization")
