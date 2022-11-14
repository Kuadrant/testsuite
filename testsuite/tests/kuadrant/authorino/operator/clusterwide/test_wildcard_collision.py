"""
Test for wildcard collisions with clusterwide authorino
"""

import pytest

from testsuite.openshift.objects.auth_config import AuthConfig


# pylint: disable = unused-argument
@pytest.fixture(scope="module")
def authorization(authorino, blame, openshift, module_label, envoy, wildcard_domain):
    """In case of Authorino, AuthConfig used for authorization"""
    auth = AuthConfig.create_instance(openshift, blame("ac"), wildcard_domain, labels={"testRun": module_label})
    auth.responses.add({"name": "header", "json": {"properties": [{"name": "anything", "value": "one"}]}})
    return auth


# pylint: disable = unused-argument
@pytest.fixture(scope="module")
def authorization2(authorino, blame, openshift2, module_label, envoy, wildcard_domain):
    """In case of Authorino, AuthConfig used for authorization"""
    auth = AuthConfig.create_instance(openshift2, blame("ac"), wildcard_domain, labels={"testRun": module_label})
    auth.responses.add({"name": "header", "json": {"properties": [{"name": "anything", "value": "two"}]}})
    return auth


@pytest.mark.parametrize(("client_fixture", "auth_fixture", "hosts"), [
    pytest.param("client", "authorization", "wildcard_domain", id="First namespace"),
    pytest.param("client2", "authorization2", [], id="Second namespace"),
])
def test_wildcard_collision(client_fixture, auth_fixture, hosts, request):
    """
    Preparation:
        - Create AuthConfig with host set to wildcard_domain
        - Create AuthConfig with host set to wildcard_domain in another project
    Test:
        - Send request to authorino
        - Assert that the correct AuthConfig was used
    """
    if hosts:
        hosts = [request.getfixturevalue(hosts)]
    client = request.getfixturevalue(client_fixture)
    response = client.get("/get")
    assert response.status_code == 200
    assert response.json()["headers"]["Header"] == '{"anything":"one"}'
    authorization = request.getfixturevalue(auth_fixture)
    assert authorization.model.status.summary.hostsReady == hosts
