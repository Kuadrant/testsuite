"""Conftest for authorino rhsso tests"""
import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth


@pytest.fixture(scope="module")
def authorization(authorization, rhsso_service_info):
    """Add RHSSO identity to AuthConfig"""
    authorization.add_oidc_identity("rhsso", rhsso_service_info.issuer_url())
    return authorization


@pytest.fixture(scope="module")
def auth(rhsso_service_info):
    """Returns RHSSO authentication object for HTTPX"""
    return HttpxOidcClientAuth(rhsso_service_info.client, "authorization",
                               rhsso_service_info.username, rhsso_service_info.password)
