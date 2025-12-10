"""Tests that HTTPRoute spec.routes.matches changes are reconciled when changed."""

from testsuite.gateway import RouteMatch, PathMatch


def test_matches(client, backend, route, hostname):
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

    with hostname.client(retry_codes={200}) as failing_client:
        response = failing_client.get("/get")
        assert response.status_code == 404, "Matches were not reconciled"

    with hostname.client(retry_codes={404, 503}) as new_client:
        response = new_client.get("/anything/get")
        assert response.status_code == 200
