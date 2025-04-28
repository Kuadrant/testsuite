"""Tests that AuthPolicy is reconciled after HTTPRoute deletion."""

import pytest

from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.kuadrant_only]


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/124")
def test_delete(client, route, hostname, authorization):
    """
    Tests that after deleting HTTPRoute, status.conditions shows it missing:
      * Test that that client works
      * Delete associated HTTPRoute
      * Test that client now does not work
      * AuthPolicy cache refresh
      * Test that status.conditions of AuthPolicy detects missing HTTPRoute
    """

    response = client.get("/get")
    assert response.status_code == 200

    deleted_route_name = route.name()
    route.delete()

    with hostname.client(retry_codes={200}) as failing_client:
        response = failing_client.get("/get")
        assert response.status_code == 404, "Removing HTTPRoute was not reconciled"

    assert authorization.refresh().wait_until(
        has_condition("Accepted", "False", "TargetNotFound", f"AuthPolicy target {deleted_route_name} was not found")
    ), f"AuthPolicy did not reach expected record status, instead it was: {authorization.model.status.condition}"
