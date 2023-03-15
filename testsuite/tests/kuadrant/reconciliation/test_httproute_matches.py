"""Tests that HTTPRoute spec.routes.matches changes are reconciled when changed."""


def test_matches(client, envoy, resilient_request):
    """
    Tests that HTTPRoute spec.routes.matches changes are reconciled when changed
      * Test that /get works
      * Set match to only /anything/*
      * Test that /get doesnt work while /anything/get does
    """

    response = client.get("/get")
    assert response.status_code == 200

    envoy.route.set_match(path_prefix="/anything")

    response = resilient_request("/get", expected_status=404)
    assert response.status_code == 404, "Matches were not reconciled"

    response = client.get("/anything/get")
    assert response.status_code == 200
