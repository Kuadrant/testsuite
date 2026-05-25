"""Basic happy-path tests for PipelinePolicy: deny action and response headers."""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def pipeline_policy(pipeline_policy):
    """Configure PipelinePolicy with deny action and response headers."""
    pipeline_policy.add_request_deny(predicate='request.url_path == "/blocked"', with_status=403)
    pipeline_policy.add_response_headers([["x-pipeline-policy", "active"]])
    return pipeline_policy


def test_allowed_path(client):
    """Request to an allowed path returns 200 with the custom response header."""
    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-pipeline-policy") == "active"


def test_blocked_path(client):
    """Request to /blocked is denied by the deny action."""
    response = client.get("/blocked")
    assert response.status_code == 403
