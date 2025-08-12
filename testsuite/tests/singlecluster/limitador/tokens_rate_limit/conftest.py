"""Conftest for TokenRateLimitPolicy tests"""

import pytest

from testsuite.backend.llm_sim import LlmSim
from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kuadrant.policy import CelExpression, CelPredicate
from testsuite.kuadrant.policy.authorization import JsonResponse, ValueFrom
from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.token_rate_limit import TokenRateLimitPolicy


@pytest.fixture(scope="module")
def user_label(blame):
    """Creates a label prefixed as user"""
    return blame("user")


@pytest.fixture(scope="module")
def free_user_api_key(create_api_key, user_label):
    """Creates API key Secret for a free user"""
    annotations = {"kuadrant.io/groups": "free", "secret.kuadrant.io/user-id": "user-1"}
    secret = create_api_key("api-key", user_label, "iamafreeuser", annotations=annotations)
    return secret


@pytest.fixture(scope="module")
def paid_user_api_key(create_api_key, user_label):
    """Creates API key Secret for a paid user"""
    annotations = {"kuadrant.io/groups": "paid", "secret.kuadrant.io/user-id": "user-2"}
    secret = create_api_key("api-key", user_label, "iamapaiduser", annotations=annotations)
    return secret


@pytest.fixture(scope="module")
def free_user_auth(free_user_api_key):
    """Valid API Key Auth for free user"""
    return HeaderApiKeyAuth(free_user_api_key)


@pytest.fixture(scope="module")
def paid_user_auth(paid_user_api_key):
    """Valid API Key Auth for paid user"""
    return HeaderApiKeyAuth(paid_user_api_key)


@pytest.fixture(scope="session")
def backend(request, cluster, blame, label, testconfig):
    """Deploys LlmSim backend"""
    image = testconfig["llm_sim"]["image"]
    llmsim = LlmSim(cluster, blame("llm-sim"), label, image)
    request.addfinalizer(llmsim.delete)
    llmsim.commit()
    return llmsim


@pytest.fixture(scope="module")
def authorization(authorization, free_user_api_key):
    """Sets AuthPolicy to validate the users API key, expose user ID/groups, and allow free/paid groups"""
    authorization.identity.add_api_key("api-key", selector=free_user_api_key.selector)
    authorization.responses.add_success_dynamic(
        "identity",
        JsonResponse(
            {
                "userid": ValueFrom("auth.identity.metadata.annotations.secret\\.kuadrant\\.io/user-id"),
                "groups": ValueFrom("auth.identity.metadata.annotations.kuadrant\\.io/groups"),
            }
        ),
    )
    authorization.authorization.add_opa_policy(
        "allow-groups",
        """
        groups := split(object.get(input.auth.identity.metadata.annotations, "kuadrant.io/groups", ""), ",")
        allow { groups[_] == "free" }
        allow { groups[_] == "paid" }
        """,
    )
    return authorization


@pytest.fixture(scope="module")
def token_rate_limit(request, cluster, blame, module_label):
    """Creates TokenRateLimitPolicy for free and paid users"""
    target_ref = request.getfixturevalue(getattr(request, "param", "route"))

    policy = TokenRateLimitPolicy.create_instance(
        cluster, blame(f"trlp-{request.param}"), target_ref, labels={"testRun": module_label}
    )

    # Free user limit - 50 tokens per 24h
    policy.add_limit(
        name="free",
        limits=[Limit(limit=50, window="24h")],
        when=[
            CelPredicate('request.path == "/v1/chat/completions"'),
            CelPredicate('auth.identity.groups.split(",").exists(g, g == "free")'),
        ],
        counters=[CelExpression("auth.identity.userid")],
    )

    # Paid user limit - 100 tokens per 24h
    policy.add_limit(
        name="paid",
        limits=[Limit(limit=100, window="24h")],
        when=[
            CelPredicate('request.path == "/v1/chat/completions"'),
            CelPredicate('auth.identity.groups.split(",").exists(g, g == "paid")'),
        ],
        counters=[CelExpression("auth.identity.userid")],
    )

    return policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, token_rate_limit):
    """Commits policies"""
    components = [authorization, token_rate_limit]
    for component in components:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()
