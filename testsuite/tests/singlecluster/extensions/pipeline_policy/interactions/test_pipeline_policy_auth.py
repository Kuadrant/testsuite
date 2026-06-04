"""Tests for PipelinePolicy interaction with AuthPolicy."""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def pipeline_policy(pipeline_policy):
    """PipelinePolicy with deny action and response header."""
    pipeline_policy.on_http_request.add_deny(predicate='request.url_path == "/blocked"', with_status=403)
    pipeline_policy.on_http_response.add_headers([["x-pipeline-policy", "active"]])
    return pipeline_policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, pipeline_policy):
    """Commit AuthPolicy and PipelinePolicy."""
    for component in [authorization, pipeline_policy]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()


def test_auth_and_pipeline_allowed(client, auth):
    """Authenticated request to allowed path passes both AuthPolicy and PipelinePolicy."""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
    assert response.headers.get("x-pipeline-policy") == "active"


def test_auth_and_pipeline_unauthorized(client):
    """Unauthenticated request is rejected by AuthPolicy before PipelinePolicy runs."""
    response = client.get("/get")
    assert response.status_code == 401
    assert response.headers.get("x-pipeline-policy") is None


def test_auth_and_pipeline_blocked_path(client, auth):
    """Authenticated request to blocked path is denied by PipelinePolicy deny action."""
    response = client.get("/blocked", auth=auth)
    assert response.status_code == 403
