"""Shared fixtures for PipelinePolicy gRPC tests."""

import pytest

from testsuite.kubernetes import Selector
from testsuite.kubernetes.deployment import Deployment
from testsuite.kubernetes.service import Service, ServicePort
from testsuite.utils.constants import HTTP_API_PORT


@pytest.fixture(scope="module")
def threat_assessment_service(request, cluster, blame, module_label, testconfig):
    """Deploys the ThreatAssessmentService gRPC backend"""
    testconfig.validators.validate(only="pipeline_policy_extension_service")
    name = blame("threat")
    match_labels = {"app": module_label, "deployment": name}

    deployment = Deployment.create_instance(
        cluster,
        name,
        container_name="threat-assessment",
        image=testconfig["pipeline_policy_extension_service"]["image"],
        ports={"grpc": HTTP_API_PORT},
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
        ports=[ServicePort(name="grpc", port=HTTP_API_PORT, targetPort="grpc")],
        labels={"app": module_label},
    )
    request.addfinalizer(service.delete)
    service.commit()
    return service


@pytest.fixture(scope="module")
def threat_service_url(threat_assessment_service):
    """gRPC URL for the threat assessment service."""
    svc = threat_assessment_service
    return f"grpc://{svc.name()}.{svc.namespace()}.svc.cluster.local:{HTTP_API_PORT}"


@pytest.fixture(scope="module")
def pipeline_policy(pipeline_policy, threat_service_url):
    """PipelinePolicy with the threat assessment gRPC action method pre-registered."""
    pipeline_policy.add_action_method(
        name="assess",
        url=threat_service_url,
        service="threat.v1.ThreatAssessmentService",
        method="AssessRequest",
        message_template="threat.v1.ThreatRequest{uri: request.path}",
    )
    return pipeline_policy
