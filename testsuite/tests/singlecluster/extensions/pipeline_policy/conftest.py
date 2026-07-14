"""Shared fixtures for PipelinePolicy testing."""

import pytest

from openshift_client import OpenShiftPythonException

from testsuite.kuadrant.extensions.pipeline_policy import PipelinePolicy


@pytest.fixture(scope="session", autouse=True)
def check_pipeline_policy_crd(cluster, skip_or_fail):
    """Skip all PipelinePolicy tests if the CRD is not installed on the cluster."""
    try:
        cluster.do_action("get", "crd/pipelinepolicies.extensions.kuadrant.io")
    except OpenShiftPythonException:
        skip_or_fail("PipelinePolicy CRD is not installed on the cluster")


@pytest.fixture(scope="module")
def pipeline_policy(cluster, blame, route):
    """PipelinePolicy targeting the test HTTPRoute"""
    return PipelinePolicy.create_instance(cluster, blame("pipeline"), route)


@pytest.fixture(scope="module", autouse=True)
def commit(request, pipeline_policy):
    """Commit and wait for PipelinePolicy to be ready."""
    request.addfinalizer(pipeline_policy.delete)
    pipeline_policy.commit()
    pipeline_policy.wait_for_ready()
