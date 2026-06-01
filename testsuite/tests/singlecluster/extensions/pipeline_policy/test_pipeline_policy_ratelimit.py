"""Tests for PipelinePolicy interaction with RateLimitPolicy."""

import pytest

from testsuite.kuadrant.policy.rate_limit import Limit

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """RateLimitPolicy with a low limit for testing."""
    rate_limit.add_limit("basic", [Limit(3, "10s")])
    return rate_limit


@pytest.fixture(scope="module")
def pipeline_policy(pipeline_policy):
    """PipelinePolicy with response header."""
    pipeline_policy.add_response_headers([["x-pipeline-policy", "active"]])
    return pipeline_policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, rate_limit, pipeline_policy):
    """Commit RateLimitPolicy and PipelinePolicy."""
    for component in [rate_limit, pipeline_policy]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()


@pytest.mark.flaky(reruns=3, reruns_delay=15)
def test_rate_limit_and_pipeline(client):
    """Rate limit is enforced alongside PipelinePolicy actions."""
    responses = client.get_many("/get", 3)
    responses.assert_all(status_code=200)
    for resp in responses:
        assert resp.headers.get("x-pipeline-policy") == "active"

    response = client.get("/get")
    assert response.status_code == 429