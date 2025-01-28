"""Conftest for kubernetes token-review tests"""

import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth


@pytest.fixture(scope="module")
def service_account_token(create_service_account, audience):
    """Create service account and request its bound token with the hostname as audience"""
    service_account = create_service_account("tkn-rev")
    return service_account.get_auth_token(audience)


@pytest.fixture(scope="module")
def auth(service_account_token):
    """Create request auth with service account token as API key"""
    return HeaderApiKeyAuth(service_account_token, "Bearer")
