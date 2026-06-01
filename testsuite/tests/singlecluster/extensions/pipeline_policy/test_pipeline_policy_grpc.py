"""Tests for PipelinePolicy grpc_method action: upstream calls and conditional execution."""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]

THREAT_THRESHOLD = 50


@pytest.fixture(scope="module")
def pipeline_policy(pipeline_policy, threat_assessment_service):  # pylint: disable=unused-argument
    """PipelinePolicy with threat assessment gRPC action and conditional headers."""
    svc_url = (
        f"grpc://{threat_assessment_service.name()}.{threat_assessment_service.namespace()}.svc.cluster.local:8080"
    )
    pipeline_policy.add_action_method(
        name="assess-threat",
        url=svc_url,
        service="threat.v1.ThreatAssessmentService",
        method="AssessRequest",
        message_template="threat.v1.ThreatRequest{uri: request.path, source_ip: source.address}",
    )

    pipeline_policy.add_request_grpc_method(
        method="assess-threat",
        var="threatResponse",
        predicate='"x-assess-threat" in request.headers',
    )
    pipeline_policy.add_request_deny(predicate='request.url_path == "/blocked"', with_status=403)
    pipeline_policy.add_request_deny(
        predicate=f"threatResponse.threat_level >= {THREAT_THRESHOLD}",
        with_status=403,
    )

    pipeline_policy.add_response_headers(
        [["x-threat-assessed", "true"]],
        predicate='"x-assess-threat" in request.headers',
    )
    pipeline_policy.add_response_headers(
        [["x-threat-assessed", "false"]],
        predicate='!("x-assess-threat" in request.headers)',
    )
    pipeline_policy.add_response_headers([["x-threat-threshold", str(THREAT_THRESHOLD)]])

    return pipeline_policy


def test_basic_grpc_upstream_call(client):
    """gRPC upstream is called when predicate matches, response var is available to subsequent actions."""
    response = client.get("/get", headers={"x-assess-threat": "true"})
    assert response.status_code == 200
    assert response.headers.get("x-threat-assessed") == "true"
    assert response.headers.get("x-threat-threshold") == str(THREAT_THRESHOLD)


def test_conditional_grpc_call_skipped(client):
    """gRPC upstream is not called when predicate does not match."""
    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-threat-assessed") == "false"
    assert response.headers.get("x-threat-threshold") == str(THREAT_THRESHOLD)


def test_grpc_response_var_deny(client):
    """Request to /blocked is denied by path-based deny rule."""
    response = client.get("/blocked")
    assert response.status_code == 403
