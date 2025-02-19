"""
Test for changing targetRef field in AuthPolicy
"""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.dnspolicy]


def test_update_auth_policy_target_ref(
    gateway2, authorization, client, client2, auth, dns_policy, dns_policy2, change_target_ref
):  # pylint: disable=unused-argument
    """Test updating the targetRef of an AuthPolicy from Gateway 1 to Gateway 2"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    response = client.get("/get")
    assert response.status_code == 401

    response = client2.get("/get")
    assert response.status_code == 200

    change_target_ref(authorization, gateway2)

    response = client2.get("/get", auth=auth)
    assert response.status_code == 200

    response = client2.get("/get")
    assert response.status_code == 401
