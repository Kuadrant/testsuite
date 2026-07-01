"""Tests that AuthPolicy and RateLimitPolicy are enforced on a GRPCRoute"""

import time

import pytest
from grpc import StatusCode

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.utils.constants import RLP_WINDOW_RESET_WAIT_BUFFERED

pytestmark = [pytest.mark.authorino, pytest.mark.limitador, pytest.mark.kuadrant_only]

LIMIT = Limit(3, "5s")  # 3 requests per 5 seconds


@pytest.fixture(scope="module")
def authorization(authorization, keycloak):
    """Add OIDC identity to AuthPolicy"""
    authorization.identity.add_oidc("keycloak", keycloak.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add basic limit to the RateLimitPolicy"""
    rate_limit.add_limit("basic", [LIMIT])
    return rate_limit


@pytest.fixture(scope="module")
def auth(keycloak):
    """Returns OIDC auth credentials"""
    return HttpxOidcClientAuth(keycloak.get_token)


def test_grpcroute(client, auth):
    """Tests AuthPolicy and RateLimitPolicy on a GRPCRoute.

    Verifies that:
    - Unauthenticated requests are rejected (UNAUTHENTICATED)
    - Authenticated requests succeed up to the rate limit
    - Requests beyond the limit are rate-limited (UNAVAILABLE)
    - After the limit window resets, requests succeed again
    """
    response = client.call("/HeadersUnary")
    assert response.status_code == StatusCode.UNAUTHENTICATED

    responses = client.call_many("/HeadersUnary", LIMIT.limit - 1, auth=auth)
    responses.assert_all(status_code=StatusCode.OK)
    assert client.call("/HeadersUnary", auth=auth).status_code == StatusCode.UNAVAILABLE

    time.sleep(RLP_WINDOW_RESET_WAIT_BUFFERED)
    assert client.call("/HeadersUnary", auth=auth).status_code == StatusCode.OK
