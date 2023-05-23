"""
Conftest for Common Feature - Caching
https://github.com/Kuadrant/authorino/blob/main/docs/user-guides/caching.md
"""

import pytest


@pytest.fixture(autouse=True)
def uuid_expectation(request, mockserver, module_label):
    """Creates Mockserver Expectation which returns random UUID"""
    mustache_template = "{ statusCode: 200, body: { 'uuid': '{{ uuid }}' } };"
    request.addfinalizer(lambda: mockserver.clear_expectation(module_label))
    return mockserver.create_template_expectation(module_label, mustache_template)


@pytest.fixture(scope="module")
def expectation_path(mockserver, module_label):
    """Returns expectation path"""
    # pylint: disable=protected-access
    return f"{mockserver.client._url}/{module_label}"


@pytest.fixture(scope="module")
def authorization(authorization):
    """Adds `aut.metadata` to the AuthJson"""
    authorization.responses.add_simple("auth.metadata")
    return authorization


@pytest.fixture(autouse=True)
def commit(request, authorization):
    """Commits all important stuff before tests"""
    request.addfinalizer(authorization.delete)
    authorization.commit()
