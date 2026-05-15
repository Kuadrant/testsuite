"""Shared fixtures for PipelinePolicy testing."""

import pytest

from testsuite.kuadrant.extensions.pipeline_policy import PipelinePolicy

# no wasm plugin gets created without having
@pytest.fixture(scope="module")
def authorization(authorization):
    """Setup AuthConfig for test"""
    authorization.identity.add_anonymous("anonymous")
    authorization.responses.add_simple("auth.identity.anonymous")
    return authorization

@pytest.fixture(scope="module")
def pipeline_policy(cluster, blame, route):
    """PipelinePolicy targeting the test HTTPRoute"""
    return PipelinePolicy.create_instance(cluster, blame("pipeline"), route)


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, pipeline_policy):
    """Commit and wait for PipelinePolicy to be ready."""
    for component in [authorization, pipeline_policy]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()
