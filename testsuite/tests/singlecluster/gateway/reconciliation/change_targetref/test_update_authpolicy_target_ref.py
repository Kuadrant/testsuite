"""
Test for changing targetRef field in AuthPolicy
"""

import time

import pytest

from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino, pytest.mark.dnspolicy]


@pytest.fixture(scope="module")
def authorization(oidc_provider, gateway, cluster, blame, module_label, route):  # pylint: disable=unused-argument
    """Overwrite the authorization fixture and attach it to the gateway"""
    policy = AuthPolicy.create_instance(cluster, blame("authz"), gateway, labels={"testRun": module_label})
    policy.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    return policy


def test_update_auth_policy_target_ref(
    route2, gateway2, authorization, client, client2, auth, dns_policy, dns_policy2, change_target_ref
):  # pylint: disable=unused-argument
    """Test updating the targetRef of an AuthPolicy from Gateway 1 to Gateway 2"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client.get("/get")
    assert response.status_code == 401

    response = client2.get("/get")
    assert response.status_code == 200

    change_target_ref(authorization, gateway2)

    time.sleep(10)  # Allow extra time for AuthPolicy enforcement to propagate

    response = client2.get("/get", auth=auth)
    assert response.status_code == 200

    response = client2.get("/get")
    assert response.status_code == 401

    response = client.get("/get")
    assert response.status_code == 200
