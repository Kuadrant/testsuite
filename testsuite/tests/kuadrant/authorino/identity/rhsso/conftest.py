"""Conftest for authorino rhsso tests"""
import pytest


@pytest.fixture(scope="session")
def oidc_provider(rhsso):
    """Fixture which enables switching out OIDC providers for individual modules"""
    return rhsso


@pytest.fixture(scope="module")
def authorization(authorization, rhsso):
    """Add RHSSO identity to AuthConfig"""
    authorization.add_oidc_identity("rhsso", rhsso.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def realm_role(rhsso, blame):
    """Creates new realm role"""
    return rhsso.realm.create_realm_role(blame("role"))
