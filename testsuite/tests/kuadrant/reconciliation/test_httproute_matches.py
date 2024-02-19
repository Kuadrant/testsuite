"""Tests that HTTPRoute spec.routes.matches changes are reconciled when changed."""

import pytest

from testsuite.gateway import RouteMatch, PathMatch

pytestmark = [pytest.mark.kuadrant_only]


def test_matches(client, backend, route):
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

    response = client.get("/get")
    assert response.status_code == 404, "Matches were not reconciled"

    response = client.get("/anything/get")
    assert response.status_code == 200
