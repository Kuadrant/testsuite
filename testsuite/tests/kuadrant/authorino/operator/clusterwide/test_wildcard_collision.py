"""
Test for wildcard collisions with clusterwide authorino
"""

import pytest

from testsuite.policy.authorization import Value, JsonResponse
from testsuite.policy.authorization.auth_config import AuthConfig

pytestmark = [pytest.mark.authorino, pytest.mark.standalone_only]


@pytest.fixture(scope="module")
def route(route, wildcard_domain, hostname):
    """Set route for wildcard domain"""
    route.add_hostname(wildcard_domain)
    route.remove_hostname(hostname.hostname)
    return route


# pylint: disable = unused-argument
@pytest.fixture(scope="module")
def authorization(authorino, blame, route, openshift, label, gateway):
    """Create AuthConfig with host set to wildcard_domain"""
    auth = AuthConfig.create_instance(openshift, blame("ac"), route, labels={"testRun": label})
    auth.responses.add_success_header("header", JsonResponse({"anything": Value("one")}))
    return auth


# pylint: disable = unused-argument
@pytest.fixture(scope="module")
def authorization2(authorino, blame, route, openshift2, label, gateway):
    """Create AuthConfig with host set to wildcard_domain in another project"""
    auth = AuthConfig.create_instance(openshift2, blame("ac"), route, labels={"testRun": label})
    auth.responses.add_success_header("header", JsonResponse({"anything": Value("two")}))
    return auth


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, authorization2):
    """Commits both AuthConfigs. Don't wait on second AuthConfig here, because it should fail to reconcile"""
    request.addfinalizer(authorization.delete)
    authorization.commit()
    authorization.wait_for_ready()

    request.addfinalizer(authorization2.delete)
    authorization2.commit()


def test_wildcard_first_authorization(client, authorization, wildcard_domain):
    """
    - Send successful request to the Authorino
    - Verify that first AuthConfig was used
    - Assert that the first AuthConfig have wildcard domain host ready
    """
    response = client.get("/get")
    assert response.status_code == 200
    assert response.json()["headers"]["Header"] == '{"anything":"one"}'

    assert authorization.model.status.summary.hostsReady == [wildcard_domain]


def test_wildcard_second_authorization(client2, authorization2):
    """
    - Assert that the second AuthConfig is not ready
    - Send successful request to the Authorino
    - Verify that first AuthConfig was used
    - Assert that the second AuthConfig have no hosts ready
    """

    def hosts_not_linked(auth_obj):
        for condition in auth_obj.model.status.conditions:
            if (
                condition.type == "Ready"
                and condition.status == "False"
                and "One or more hosts are not linked to the resource" in condition.message
                and condition.reason == "HostsNotLinked"
            ):
                return True
        return False

    assert authorization2.wait_until(hosts_not_linked)

    response = client2.get("/get")
    assert response.status_code == 200
    assert response.json()["headers"]["Header"] == '{"anything":"one"}'

    assert authorization2.model.status.summary.hostsReady == []
