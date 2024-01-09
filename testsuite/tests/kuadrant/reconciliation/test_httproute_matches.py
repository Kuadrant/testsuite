"""Tests that HTTPRoute spec.routes.matches changes are reconciled when changed."""
from testsuite.gateway import RouteMatch, PathMatch


def test_matches(client, backend, route, resilient_request):
    """
    Tests that HTTPRoute spec.routes.matches changes are reconciled when changed
      * Test that /get works
      * Set match to only /anything/*
      * Test that /get doesnt work while /anything/get does
    """

    response = client.get("/get")
    assert response.status_code == 200

    route.remove_all_rules()
    route.add_rule(backend, RouteMatch(path=PathMatch(value="/anything")))

    response = resilient_request("/get", expected_status=404)
    assert response.status_code == 404, "Matches were not reconciled"

    response = client.get("/anything/get")
    assert response.status_code == 200
