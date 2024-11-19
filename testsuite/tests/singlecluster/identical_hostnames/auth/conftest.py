import pytest


@pytest.fixture(scope="module")
def authorization(authorization):
    """2nd Authorization object"""
    authorization.authorization.add_opa_policy("rego", "allow = true")
    return authorization


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, authorization2):
    """Ensure Authorization is created. All commits are handled manually in these tests"""
    for auth in [authorization, authorization2]:
        if auth is not None:
            request.addfinalizer(auth.delete)
            auth.commit()
            auth.wait_for_accepted()
