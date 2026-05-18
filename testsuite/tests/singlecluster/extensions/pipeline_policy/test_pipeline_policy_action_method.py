import pytest

from testsuite.kubernetes import Selector
from testsuite.kubernetes.deployment import Deployment
from testsuite.kubernetes.service import Service, ServicePort


@pytest.fixture(scope="module")
def threat_assessment_service(request, cluster, blame, module_label):
    """Deploys the ThreatAssessmentService gRPC backend"""
    name = blame("threat")
    match_labels = {"app": module_label, "deployment": name}

    deployment = Deployment.create_instance(
        cluster,
        name,
        container_name="threat-assessment",
        image="quay.io/kuadrant/threat-assessment-service:latest",
        ports={"grpc": 8080},
        selector=Selector(matchLabels=match_labels),
        labels={"app": module_label},
    )
    request.addfinalizer(deployment.delete)
    deployment.commit()
    deployment.wait_for_ready()

    service = Service.create_instance(
        cluster,
        name,
        selector=match_labels,
        ports=[ServicePort(name="grpc", port=8080, targetPort="grpc")],
        labels={"app": module_label},
    )
    request.addfinalizer(service.delete)
    service.commit()
    return service


THREAT_THRESHOLD = 50


@pytest.fixture(scope="module")
def pipeline_policy(pipeline_policy, threat_assessment_service):  # pylint: disable=unused-argument
    """Configure PipelinePolicy with threat assessment gRPC action and conditional headers."""
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

    pipeline_policy.add_request_allow('request.url_path != "/blocked"')
    pipeline_policy.add_request_grpc_method(
        method="assess-threat",
        var="threatResponse",
        intention=f"threatResponse.threat_level < {THREAT_THRESHOLD}",
        predicate='"x-assess-threat" in request.headers',
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


def test_allowed_path(client):
    """Request to an allowed path returns 200 without threat assessment."""
    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-threat-assessed") == "false"
    assert response.headers.get("x-threat-threshold") == str(THREAT_THRESHOLD)


def test_blocked_path(client):
    """Request to /blocked is denied by the allow rule."""
    response = client.get("/blocked")
    assert response.status_code == 403


def test_threat_assessment_safe(client):
    """Request with x-assess-threat header to a safe path passes threat check."""
    response = client.get("/get", headers={"x-assess-threat": "true"})
    assert response.status_code == 200
    assert response.headers.get("x-threat-assessed") == "true"
    assert response.headers.get("x-threat-threshold") == str(THREAT_THRESHOLD)
