"""Conftest for TRLP reservation tests with multiple users"""

import pytest

from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kuadrant.policy import CelExpression
from testsuite.kuadrant.policy.authorization import JsonResponse, ValueFrom
from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.token_rate_limit import Reservation, TokenRateLimitPolicy

LIMIT = Limit(limit=200, window="20s")


@pytest.fixture(scope="module")
def user_label(blame):
    """Creates a label prefixed as user"""
    return blame("user")


@pytest.fixture(scope="module")
def user1_api_key(create_api_key, user_label, blame):
    """Creates API key Secret for the first user"""
    annotations = {"secret.kuadrant.io/user-id": blame("user1")}
    return create_api_key("api-key", user_label, "iamuserone", annotations=annotations)


@pytest.fixture(scope="module")
def user2_api_key(create_api_key, user_label, blame):
    """Creates API key Secret for the second user"""
    annotations = {"secret.kuadrant.io/user-id": blame("user2")}
    return create_api_key("api-key", user_label, "iamusertwo", annotations=annotations)


@pytest.fixture(scope="module")
def user1_auth(user1_api_key):
    """Valid API Key Auth for the first user"""
    return HeaderApiKeyAuth(user1_api_key)


@pytest.fixture(scope="module")
def user2_auth(user2_api_key):
    """Valid API Key Auth for the second user"""
    return HeaderApiKeyAuth(user2_api_key)


@pytest.fixture(scope="module")
def authorization(authorization, user1_api_key):
    """Sets AuthPolicy to validate the users API key and expose the user ID"""
    authorization.identity.add_api_key("api-key", selector=user1_api_key.selector)
    authorization.responses.add_success_dynamic(
        "identity",
        JsonResponse({"userid": ValueFrom("auth.identity.metadata.annotations.secret\\.kuadrant\\.io/user-id")}),
    )
    return authorization


@pytest.fixture(scope="module")
def token_rate_limit(cluster, blame, route, module_label):
    """Creates TRLP with a single reservation-enabled limit, counted independently per user"""
    policy = TokenRateLimitPolicy.create_instance(cluster, blame("trlp"), route, labels={"testRun": module_label})
    policy.add_limit(
        name="per-user",
        limits=[LIMIT],
        counters=[CelExpression("auth.identity.userid")],
    )
    policy.set_reservation("per-user", Reservation(amount=50, ttl='duration("20s")'))
    return policy
