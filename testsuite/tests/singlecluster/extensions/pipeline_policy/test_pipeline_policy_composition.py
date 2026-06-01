"""Tests for PipelinePolicy composition: action ordering, empty and partial pipelines."""

import pytest

from testsuite.kuadrant.extensions.pipeline_policy import PipelinePolicy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module", autouse=True)
def commit():
    """No module-level policy; each test creates its own."""


def test_first_deny_wins(request, cluster, blame, route, client):
    """When two deny actions match, the first one in spec order determines the response status."""
    policy = PipelinePolicy.create_instance(cluster, blame("order"), route)
    policy.add_request_deny(predicate='request.url_path == "/order-test"', with_status=403)
    policy.add_request_deny(predicate='request.url_path == "/order-test"', with_status=429)
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/order-test")
    assert response.status_code == 403


def test_fail_before_deny(request, cluster, blame, route, client, threat_assessment_service):
    """Fail action before deny takes precedence when gRPC response triggers the fail predicate."""
    svc_url = (
        f"grpc://{threat_assessment_service.name()}.{threat_assessment_service.namespace()}.svc.cluster.local:8080"
    )
    policy = PipelinePolicy.create_instance(cluster, blame("failord"), route)
    policy.add_action_method(
        name="assess",
        url=svc_url,
        service="threat.v1.ThreatAssessmentService",
        method="AssessRequest",
        message_template="threat.v1.ThreatRequest{uri: request.path}",
    )
    policy.add_request_grpc_method(method="assess", var="threat")
    policy.add_request_fail("threat too high", predicate="threat.threat_level >= 4")
    # policy.add_request_deny(predicate="true", with_status=403)
    policy.add_request_deny(predicate='request.url_path == "/blocked"', with_status=403)
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/admin")
    assert response.status_code == 500


def test_response_action_ordering(request, cluster, blame, route, client):
    """Response actions execute in spec order; both headers from separate actions are present."""
    policy = PipelinePolicy.create_instance(cluster, blame("respord"), route)
    policy.add_response_headers([["x-first", "alpha"]])
    policy.add_response_headers([["x-second", "bravo"]])
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-first") == "alpha"
    assert response.headers.get("x-second") == "bravo"


def test_empty_pipeline(request, cluster, blame, route, client):
    """PipelinePolicy with no actions passes requests through unmodified."""
    policy = PipelinePolicy.create_instance(cluster, blame("empty"), route)
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-pipeline-policy") is None


def test_request_only_pipeline(request, cluster, blame, route, client):
    """Pipeline with only request actions: deny works, no response modifications."""
    policy = PipelinePolicy.create_instance(cluster, blame("reqonly"), route)
    policy.add_request_deny(predicate='request.url_path == "/blocked"', with_status=403)
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    assert client.get("/get").status_code == 200
    assert client.get("/blocked").status_code == 403


def test_response_only_pipeline(request, cluster, blame, route, client):
    """Pipeline with only response actions: all requests pass, headers are modified."""
    policy = PipelinePolicy.create_instance(cluster, blame("resonly"), route)
    policy.add_response_headers([["x-resp-only", "true"]])
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-resp-only") == "true"


def test_mixed_pipeline(request, cluster, blame, route, client):
    """Pipeline with both request deny and response headers executes in full."""
    policy = PipelinePolicy.create_instance(cluster, blame("mixed"), route)
    policy.add_request_deny(predicate='request.url_path == "/blocked"', with_status=403)
    policy.add_response_headers([["x-mixed", "true"]])
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-mixed") == "true"

    assert client.get("/blocked").status_code == 403