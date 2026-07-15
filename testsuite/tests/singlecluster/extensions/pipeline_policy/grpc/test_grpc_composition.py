"""Tests for PipelinePolicy composition of gRPC actions with deny and fail."""

import pytest

from testsuite.kuadrant.extensions.pipeline_policy import PipelinePolicy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module", autouse=True)
def commit():
    """No module-level policy; each test creates its own."""


@pytest.fixture(scope="module")
def create_grpc_policy(cluster, blame, route, threat_service_url, module_label):
    """Factory for creating a PipelinePolicy with the assess gRPC action pre-registered."""

    def _create(name):
        policy = PipelinePolicy.create_instance(cluster, blame(name), route, labels={"testRun": module_label})
        policy.add_action_method(
            name="assess",
            url=threat_service_url,
            service="threat.v1.ThreatAssessmentService",
            method="AssessRequest",
            message_template="threat.v1.ThreatRequest{uri: request.path}",
        )
        policy.on_http_request.add_grpc_method(method="assess", var="threat")
        return policy

    return _create


def test_fail_before_deny(request, create_grpc_policy, client):
    """Fail action terminates the chain before the deny action when gRPC response triggers the fail predicate."""
    policy = create_grpc_policy("failord")
    policy.on_http_request.add_fail("threat too high", predicate="threat.threat_level >= 4")
    policy.on_http_request.add_deny(predicate='request.url_path == "/blocked"', with_status=403)
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/admin")
    assert response.status_code == 500


def test_deny_after_grpc_call(request, create_grpc_policy, client):
    """Deny action after gRPC call works when the deny predicate matches."""
    policy = create_grpc_policy("grpc-deny")
    policy.on_http_request.add_deny(predicate='request.url_path == "/blocked"', with_status=403)
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/blocked")
    assert response.status_code == 403


def test_deny_based_on_grpc_var(request, create_grpc_policy, client):
    """Deny action using gRPC response variable denies requests when threat level is high."""
    policy = create_grpc_policy("grpc-var-deny")
    policy.on_http_request.add_deny(predicate="threat.threat_level >= 4", with_status=403)
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/admin")
    assert response.status_code == 403

    response = client.get("/get")
    assert response.status_code == 200


def test_deny_with_dynamic_body(request, create_grpc_policy, client):
    """Deny action with CEL expression in withBody interpolates gRPC response variable."""
    policy = create_grpc_policy("dyn-body")
    policy.on_http_request.add_deny(
        predicate="threat.threat_level >= 4",
        with_status=403,
        with_body="'blocked: threat level ' + string(threat.threat_level)",
    )
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/admin")
    assert response.status_code == 403
    assert "blocked: threat level" in response.text
