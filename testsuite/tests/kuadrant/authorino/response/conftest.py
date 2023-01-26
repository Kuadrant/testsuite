"""Conftest for custom Response tests"""
import pytest


@pytest.fixture(scope="module")
def responses():
    """Returns responses to be added to the AuthConfig"""
    return []


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def authorization_name(blame, responses):
    """Ensure for every response we have a unique authorization"""
    return blame("authz")


@pytest.fixture(scope="module")
def authorization(authorization, responses):
    """Add response to Authorization"""
    for response in responses:
        authorization.responses.add(response)
    return authorization


# pylint: disable=unused-argument
@pytest.fixture(scope="function", autouse=True)
def commit(request, authorization, responses):
    """Commits all important stuff before tests"""
    request.addfinalizer(authorization.delete)
    authorization.commit()
