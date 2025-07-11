import pytest

from testsuite.kuadrant.policy.authorization import JsonResponse, ValueFrom

@pytest.fixture(scope="module")
def user_label(blame):
    """Creates a label prefixed as user"""
    return blame("user")

@pytest.fixture(scope="module")
def free_user_api_key(create_api_key, user_label):
    """Creates API key Secret for a free user"""
    annotations = {
        "kuadrant.io/groups": "free",
        "secret.kuadrant.io/user-id": "user-1"
    }
    secret = create_api_key("api-key", user_label, "iamafreeuser", annotations=annotations)
    return secret

@pytest.fixture(scope="module")
def paid_user_api_key(create_api_key, user_label):
    """Creates API key Secret for a paid user"""
    annotations = {
        "kuadrant.io/groups": "paid",
        "secret.kuadrant.io/user-id": "user-2"
    }
    secret = create_api_key("api-key", user_label, "iamapaiduser", annotations=annotations)
    return secret

@pytest.fixture(scope="module")
def authorization(authorization, user_label, free_user_api_key):
    authorization.identity.add_api_key("api-key", selector=free_user_api_key.selector)
    authorization.responses.add_success_dynamic(
        "identity", JsonResponse({"anonymous": ValueFrom("{auth.identity.anonymous}")})
    )
    authorization.authorization.add_opa_policy(
        "allow-groups",
        """
        groups := split(object.get(input.auth.identity.metadata.annotations, "kuadrant.io/groups", ""), ",")
        allow { groups[_] = "free" }
        allow { groups[_] = "paid" }
        """
    )
    return authorization

@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization):
    request.addfinalizer(authorization.delete)
    authorization.commit()
    authorization.wait_for_ready()