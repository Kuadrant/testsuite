"""Basic happy-path tests for PipelinePolicy: status conditions, deny action and response headers."""

import pytest

from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def pipeline_policy(pipeline_policy):
    """Configure PipelinePolicy with deny action and response headers."""
    pipeline_policy.on_http_request.add_deny(predicate='request.url_path == "/blocked"', with_status=403)
    pipeline_policy.on_http_response.add_headers([["x-pipeline-policy", "active"]])
    return pipeline_policy


def test_status_accepted(pipeline_policy):
    """PipelinePolicy reports Accepted: True after commit."""
    assert pipeline_policy.wait_until(
        has_condition("Accepted", "True"),
        timelimit=30,
    ), f"Policy not Accepted, status: {pipeline_policy.refresh().model.status.conditions}"


def test_status_enforced(pipeline_policy):
    """PipelinePolicy reports Enforced: True after commit."""
    assert pipeline_policy.wait_until(
        has_condition("Enforced", "True"),
        timelimit=30,
    ), f"Policy not Enforced, status: {pipeline_policy.refresh().model.status.conditions}"


def test_allowed_path(client):
    """Request to an allowed path returns 200 with the custom response header."""
    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-pipeline-policy") == "active"


def test_blocked_path(client):
    """Request to /blocked is denied by the deny action."""
    response = client.get("/blocked")
    assert response.status_code == 403
