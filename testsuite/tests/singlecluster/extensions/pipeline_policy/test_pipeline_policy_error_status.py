"""Tests that PipelinePolicy surfaces error status conditions for invalid action method configurations."""

import pytest

from testsuite.kubernetes import Selector
from testsuite.kubernetes.deployment import Deployment
from testsuite.kubernetes.service import Service, ServicePort
from testsuite.kuadrant.extensions.pipeline_policy import PipelinePolicy
from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization):
    """Only commit authorization; each test creates its own policy with bad configuration."""
    request.addfinalizer(authorization.delete)
    authorization.commit()
    authorization.wait_for_ready()


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


def test_nonexistent_url(request, cluster, blame, route):
    """PipelinePolicy reports error when action method URL points to a non-existent service."""
    policy = PipelinePolicy.create_instance(cluster, blame("bad-url"), route)
    policy.add_action_method(
        name="bad-method",
        url="grpc://does-not-exist.default.svc.cluster.local:8080",
        service="threat.v1.ThreatAssessmentService",
        method="AssessRequest",
        message_template="threat.v1.ThreatRequest{uri: request.path}",
    )
    policy.add_request_allow('request.url_path != "/blocked"')
    policy.add_request_grpc_method(method="bad-method")

    request.addfinalizer(policy.delete)
    policy.commit()

    # TODO: add expected message assertion
    assert policy.wait_until(
        has_condition("Accepted", "False", "Unknown"),
        timelimit=60,
    ), f"Policy did not reach expected error status, instead: {policy.refresh().model.status.conditions}"


def test_wrong_service_name(request, cluster, blame, route, threat_assessment_service):
    """PipelinePolicy reports error when action method references a non-existent gRPC service name."""
    svc_url = (
        f"grpc://{threat_assessment_service.name()}" f".{threat_assessment_service.namespace()}.svc.cluster.local:8080"
    )
    policy = PipelinePolicy.create_instance(cluster, blame("bad-svc"), route)
    policy.add_action_method(
        name="bad-service",
        url=svc_url,
        service="nonexistent.v1.FakeService",
        method="DoSomething",
        message_template="nonexistent.v1.FakeRequest{uri: request.path}",
    )
    policy.add_request_allow('request.url_path != "/blocked"')
    policy.add_request_grpc_method(method="bad-service")

    request.addfinalizer(policy.delete)
    policy.commit()

    # TODO: add expected message assertion
    assert policy.wait_until(
        has_condition("Accepted", "False", "Unknown"),
        timelimit=60,
    ), f"Policy did not reach expected error status, instead: {policy.refresh().model.status.conditions}"


def test_wrong_method_name(request, cluster, blame, route, threat_assessment_service):
    """PipelinePolicy reports error when action method references a non-existent gRPC method."""
    svc_url = (
        f"grpc://{threat_assessment_service.name()}" f".{threat_assessment_service.namespace()}.svc.cluster.local:8080"
    )
    policy = PipelinePolicy.create_instance(cluster, blame("bad-meth"), route)
    policy.add_action_method(
        name="wrong-method",
        url=svc_url,
        service="threat.v1.ThreatAssessmentService",
        method="NonExistentMethod",
        message_template="threat.v1.ThreatRequest{uri: request.path}",
    )
    policy.add_request_allow('request.url_path != "/blocked"')
    policy.add_request_grpc_method(method="wrong-method")

    request.addfinalizer(policy.delete)
    policy.commit()

    # TODO: add expected message assertion
    assert policy.wait_until(
        has_condition("Accepted", "False", "Unknown"),
        timelimit=60,
    ), f"Policy did not reach expected error status, instead: {policy.refresh().model.status.conditions}"
