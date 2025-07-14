import pytest

from testsuite.backend.llm_sim import LlmSim
from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kuadrant.policy.authorization import JsonResponse, ValueFrom
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
def authorization(authorization, user_label, free_user_api_key):
    authorization.identity.add_api_key("api-key", selector=free_user_api_key.selector)
    authorization.responses.add_success_dynamic(
        "identity",
        JsonResponse({"userid": ValueFrom("auth.identity.metadata.annotations.secret\\.kuadrant\\.io/user-id")}),
    )
    authorization.authorization.add_opa_policy(
        "allow-groups",
        """
        groups := split(object.get(input.auth.identity.metadata.annotations, "kuadrant.io/groups", ""), ",")
        allow { groups[_] = "free" }
        allow { groups[_] = "paid" }
        """,
    )
    return authorization


@pytest.fixture(scope="module")
def token_rate_limit(cluster, blame, label):
    """Creates TokenRateLimitPolicy"""
    policy = TokenRateLimitPolicy.create_instance(cluster, blame("trlp"), label)
    return policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, token_rate_limit):
    components = [authorization, token_rate_limit]
    for component in components:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()
