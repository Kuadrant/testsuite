"""Tests for PipelinePolicy lifecycle: status conditions, delete, and update."""

import pytest

from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def pipeline_policy(pipeline_policy):
    """PipelinePolicy with deny action and response header."""
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


def test_update_policy(client, pipeline_policy):
    """Adding a new response header via policy update propagates to traffic."""
    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-pipeline-policy") == "active"
    assert response.headers.get("x-pipeline-updated") is None

    pipeline_policy.on_http_response.add_headers([["x-pipeline-updated", "true"]])
    pipeline_policy.wait_for_ready()

    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-pipeline-policy") == "active"
    assert response.headers.get("x-pipeline-updated") == "true"


@pytest.mark.flaky(reruns=0)
def test_delete_policy(client, pipeline_policy):
    """After deleting the PipelinePolicy, the CR is removed from the cluster."""
    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-pipeline-policy") == "active"

    pipeline_policy.delete()
    assert pipeline_policy.wait_until(lambda obj: not obj.exists(), timelimit=30), "PipelinePolicy was not deleted"
