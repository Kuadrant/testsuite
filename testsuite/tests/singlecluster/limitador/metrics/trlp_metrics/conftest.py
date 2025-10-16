"""Conftest for TokenRateLimitPolicy metrics tests"""

import pytest

from testsuite.backend.llm_sim import LlmSim
from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kuadrant.extensions.telemetry_policy import TelemetryPolicy
from testsuite.kuadrant.policy import CelExpression, CelPredicate
from testsuite.kuadrant.policy.authorization import JsonResponse, ValueFrom
from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.kuadrant.policy.token_rate_limit import TokenRateLimitPolicy

FREE_USER_LIMIT = Limit(limit=15, window="30s")
PAID_USER_LIMIT = Limit(limit=30, window="60s")

USERS = ("free", "paid")
MODEL_NAME = "meta-llama/Llama-3.1-8B-Instruct"


@pytest.fixture(scope="module")
def backend(request, cluster, blame, label, testconfig):
    """Deploys LlmSim backend"""
    image = testconfig["llm_sim"]["image"]
    llmsim = LlmSim(cluster, blame("llm-sim"), "meta-llama/Llama-3.1-8B-Instruct", label, image)
    request.addfinalizer(llmsim.delete)
    llmsim.commit()
    return llmsim


@pytest.fixture(scope="module")
def user_data(free_user_api_key, paid_user_api_key, free_user_auth, paid_user_auth):
    """Provides free/paid user data for parametrized tests"""
    return {
        "free": {
            "api_key": free_user_api_key,
            "auth": free_user_auth,
            "group": "free",
            "user_id": free_user_api_key.model.metadata.annotations["secret.kuadrant.io/user-id"],
        },
        "paid": {
            "api_key": paid_user_api_key,
            "auth": paid_user_auth,
            "group": "paid",
            "user_id": paid_user_api_key.model.metadata.annotations["secret.kuadrant.io/user-id"],
        },
    }


@pytest.fixture(scope="module")
def user_label(blame):
    """Creates a label prefixed as user"""
    return blame("user")


@pytest.fixture(scope="module")
def free_user_api_key(create_api_key, user_label, blame):
    """Creates API key Secret for a free user"""
    annotations = {"kuadrant.io/groups": "free", "secret.kuadrant.io/user-id": blame("free-user")}
    return create_api_key("api-key", user_label, "iamafreeuser", annotations=annotations)


@pytest.fixture(scope="module")
def paid_user_api_key(create_api_key, user_label, blame):
    """Creates API key Secret for a paid user"""
    annotations = {"kuadrant.io/groups": "paid", "secret.kuadrant.io/user-id": blame("paid-user")}
    return create_api_key("api-key", user_label, "iamapaiduser", annotations=annotations)


@pytest.fixture(scope="module")
def free_user_auth(free_user_api_key):
    """Valid API Key Auth for free user"""
    return HeaderApiKeyAuth(free_user_api_key)


@pytest.fixture(scope="module")
def paid_user_auth(paid_user_api_key):
    """Valid API Key Auth for paid user"""
    return HeaderApiKeyAuth(paid_user_api_key)


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
def token_rate_limit(cluster, blame, module_label, route):
    """Creates TokenRateLimitPolicy for free and paid users"""
    policy = TokenRateLimitPolicy.create_instance(cluster, blame("trlp"), route, labels={"testRun": module_label})

    policy.add_limit(
        name="free",
        limits=[FREE_USER_LIMIT],
        when=[
            CelPredicate('request.path == "/v1/chat/completions"'),
            CelPredicate('auth.identity.groups.split(",").exists(g, g == "free")'),
        ],
        counters=[CelExpression("auth.identity.userid")],
    )

    policy.add_limit(
        name="paid",
        limits=[PAID_USER_LIMIT],
        when=[
            CelPredicate('request.path == "/v1/chat/completions"'),
            CelPredicate('auth.identity.groups.split(",").exists(g, g == "paid")'),
        ],
        counters=[CelExpression("auth.identity.userid")],
    )

    return policy


@pytest.fixture(scope="module")
def telemetry_policy(cluster, blame, module_label, gateway):
    """Add a telemetry policy to expose user and group labels in metrics"""
    policy = TelemetryPolicy.create_instance(cluster, blame("user-group"), gateway, labels={"testRun": module_label})

    policy.add_label("user", "auth.identity.userid")
    policy.add_label("group", "auth.identity.groups")
    policy.add_label("model", 'responseBodyJSON("/model")')

    return policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, token_rate_limit, telemetry_policy):
    """Commits policies"""
    components = [authorization, token_rate_limit, telemetry_policy]
    for component in components:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()
