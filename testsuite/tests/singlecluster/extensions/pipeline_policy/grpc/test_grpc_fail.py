"""Tests for PipelinePolicy fail action triggered by gRPC response variables."""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def pipeline_policy(pipeline_policy):
    """PipelinePolicy with gRPC call and fail action based on threat level."""
    pipeline_policy.on_http_request.add_grpc_method(method="assess", var="threat")
    pipeline_policy.on_http_request.add_fail(
        "threat level too high",
        predicate="threat.threat_level >= 4",
    )
    pipeline_policy.on_http_response.add_headers([["x-pipeline-active", "true"]])
    return pipeline_policy


def test_fail_triggers_on_high_threat(client):
    """Fail action triggers when gRPC response threat_level meets the threshold and terminates the chain."""
    response = client.get("/admin")
    assert response.status_code == 500
    assert response.headers.get("x-pipeline-active") is None


def test_fail_does_not_trigger_on_low_threat(client):
    """Fail action does not trigger when gRPC response threat_level is below the threshold."""
    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-pipeline-active") == "true"
