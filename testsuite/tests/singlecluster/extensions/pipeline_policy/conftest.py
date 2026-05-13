"""Shared fixtures for PipelinePolicy testing."""

import pytest

from testsuite.kuadrant.extensions.pipeline_policy import PipelinePolicy


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
