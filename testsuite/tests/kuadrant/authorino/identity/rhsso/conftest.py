"""Conftest for authorino rhsso tests"""
import pytest


@pytest.fixture(scope="module")
def authorization(authorization, rhsso_service_info):
    """Add RHSSO identity to AuthConfig"""
    authorization.add_oidc_identity("rhsso", rhsso_service_info.issuer_url())
    return authorization
