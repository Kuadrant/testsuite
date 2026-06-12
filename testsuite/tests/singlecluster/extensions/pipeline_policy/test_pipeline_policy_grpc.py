"""Tests for PipelinePolicy grpc_method action: upstream calls and conditional execution."""

import pytest

from testsuite.utils.constants import THREAT_ASSESSMENT_THRESHOLD

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


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

    pipeline_policy.on_http_request.add_grpc_method(
        method="assess-threat",
        var="threatResponse",
        predicate='"x-assess-threat" in request.headers',
    )
    pipeline_policy.on_http_request.add_deny(predicate='request.url_path == "/blocked"', with_status=403)
    pipeline_policy.on_http_request.add_deny(
        predicate=f"threatResponse.threat_level >= {THREAT_ASSESSMENT_THRESHOLD}",
        with_status=403,
    )

    pipeline_policy.on_http_response.add_headers(
        [["x-threat-assessed", "true"]],
        predicate='"x-assess-threat" in request.headers',
    )
    pipeline_policy.on_http_response.add_headers(
        [["x-threat-assessed", "false"]],
        predicate='!("x-assess-threat" in request.headers)',
    )
    pipeline_policy.on_http_response.add_headers([["x-threat-threshold", str(THREAT_ASSESSMENT_THRESHOLD)]])

    return pipeline_policy


def test_basic_grpc_upstream_call(client):
    """gRPC upstream is called when predicate matches, response var is available to subsequent actions."""
    response = client.get("/get", headers={"x-assess-threat": "true"})
    assert response.status_code == 200
    assert response.headers.get("x-threat-assessed") == "true"
    assert response.headers.get("x-threat-threshold") == str(THREAT_ASSESSMENT_THRESHOLD)


def test_conditional_grpc_call_skipped(client):
    """gRPC upstream is not called when predicate does not match."""
    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-threat-assessed") == "false"
    assert response.headers.get("x-threat-threshold") == str(THREAT_ASSESSMENT_THRESHOLD)
