"""Tests for PipelinePolicy interaction with both AuthPolicy and RateLimitPolicy."""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy.rate_limit import Limit

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """AuthPolicy with OIDC identity verification."""
    authorization.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Valid OIDC authentication for requests."""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """RateLimitPolicy with a low limit for testing."""
    rate_limit.add_limit("basic", [Limit(3, "10s")])
    return rate_limit


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


def test_all_policies_allowed(client, auth):
    """Authenticated request passes auth, rate limit, and gets PipelinePolicy header."""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
    assert response.headers.get("x-pipeline-policy") == "active"


def test_all_policies_unauthorized(client):
    """Unauthenticated request is rejected by AuthPolicy before other policies run."""
    response = client.get("/get")
    assert response.status_code == 401
    assert response.headers.get("x-pipeline-policy") is None


def test_all_policies_blocked_path(client, auth):
    """Authenticated request to blocked path is denied by PipelinePolicy deny action."""
    response = client.get("/blocked", auth=auth)
    assert response.status_code == 403


@pytest.mark.flaky(reruns=3, reruns_delay=15)
def test_all_policies_rate_limited(client, auth):
    """Rate limit is enforced alongside AuthPolicy and PipelinePolicy."""
    responses = client.get_many("/get", 3, auth=auth)
    responses.assert_all(status_code=200)
    for resp in responses:
        assert resp.headers.get("x-pipeline-policy") == "active"

    response = client.get("/get", auth=auth)
    assert response.status_code == 429
