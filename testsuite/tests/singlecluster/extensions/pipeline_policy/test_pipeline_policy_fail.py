"""Tests for PipelinePolicy fail action triggered by gRPC response variables."""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def pipeline_policy(pipeline_policy, threat_assessment_service):
    """PipelinePolicy with gRPC call and fail action based on threat level."""
    svc_url = (
        f"grpc://{threat_assessment_service.name()}.{threat_assessment_service.namespace()}.svc.cluster.local:8080"
    )
    pipeline_policy.add_action_method(
        name="assess",
        url=svc_url,
        service="threat.v1.ThreatAssessmentService",
        method="AssessRequest",
        message_template="threat.v1.ThreatRequest{uri: request.path}",
    )
    pipeline_policy.add_request_grpc_method(method="assess", var="threat")
    pipeline_policy.add_request_fail(
        "threat level too high",
        predicate="threat.threat_level >= 4",
    )
    pipeline_policy.add_response_headers([["x-pipeline-active", "true"]])
    return pipeline_policy


def test_fail_triggers_on_high_threat(client):
    """Fail action triggers when gRPC response threat_level meets the threshold."""
    response = client.get("/admin")
    assert response.status_code == 500


def test_fail_does_not_trigger_on_low_threat(client):
    """Fail action does not trigger when gRPC response threat_level is below the threshold."""
    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-pipeline-active") == "true"


def test_fail_no_response_headers_on_failure(client):
    """Response headers are not added when fail action terminates the chain."""
    response = client.get("/admin")
    assert response.status_code == 500
    assert response.headers.get("x-pipeline-active") is None