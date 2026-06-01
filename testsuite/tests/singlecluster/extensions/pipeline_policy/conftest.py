"""Shared fixtures for PipelinePolicy testing."""

import pytest

from testsuite.kubernetes import Selector
from testsuite.kubernetes.deployment import Deployment
from testsuite.kubernetes.service import Service, ServicePort
from testsuite.kuadrant.extensions.pipeline_policy import PipelinePolicy


@pytest.fixture(scope="module")
def pipeline_policy(cluster, blame, route):
    """PipelinePolicy targeting the test HTTPRoute"""
    return PipelinePolicy.create_instance(cluster, blame("pipeline"), route)


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


@pytest.fixture(scope="module", autouse=True)
def commit(request, pipeline_policy):
    """Commit and wait for PipelinePolicy to be ready."""
    for component in [pipeline_policy]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()
