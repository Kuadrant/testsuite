"""Tests for PipelinePolicy interaction with both AuthPolicy and RateLimitPolicy."""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def pipeline_policy(pipeline_policy):
    """PipelinePolicy with deny action and response header."""
    pipeline_policy.on_http_request.add_deny(predicate='request.url_path == "/blocked"', with_status=403)
    pipeline_policy.on_http_response.add_headers([["x-pipeline-policy", "active"]])
    return pipeline_policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, rate_limit, pipeline_policy):
    """Commit AuthPolicy, RateLimitPolicy, and PipelinePolicy."""
    for component in [authorization, rate_limit, pipeline_policy]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()


@pytest.mark.flaky(reruns=3, reruns_delay=15)
def test_all_policies_rate_limited(client, auth):
    """Rate limit is enforced alongside AuthPolicy and PipelinePolicy."""
    responses = client.get_many("/get", 3, auth=auth)
    responses.assert_all(status_code=200)
    for resp in responses:
        assert resp.headers.get("x-pipeline-policy") == "active"

    response = client.get("/get", auth=auth)
    assert response.status_code == 429
