"""Tests for PipelinePolicy deny action variants in request and response phases."""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def pipeline_policy(pipeline_policy):
    """PipelinePolicy with multiple deny configurations covering all deny variants."""
    # Path-based deny
    pipeline_policy.on_http_request.add_deny(predicate='request.url_path == "/deny-path"', with_status=403)
    # Header-based deny
    pipeline_policy.on_http_request.add_deny(predicate='"x-deny-me" in request.headers', with_status=401)
    # Custom status code
    pipeline_policy.on_http_request.add_deny(predicate='request.url_path == "/custom-status"', with_status=429)
    # Custom headers
    pipeline_policy.on_http_request.add_deny(
        predicate='request.url_path == "/custom-headers"',
        with_status=403,
        with_headers='[["x-deny-reason", "blocked"]]',
    )
    # Custom body
    pipeline_policy.on_http_request.add_deny(
        predicate='request.url_path == "/custom-body"',
        with_status=403,
        with_body="Access denied",
    )
    # All response fields
    pipeline_policy.on_http_request.add_deny(
        predicate='request.url_path == "/custom-all"',
        with_status=451,
        with_headers='[["x-deny-reason", "full-custom"]]',
        with_body="Fully customized denial",
    )
    # Response phase deny — status override
    pipeline_policy.on_http_response.add_deny(
        predicate='"x-override-code" in request.headers',
        with_status=503,
    )
    # Response phase deny — all fields
    pipeline_policy.on_http_response.add_deny(
        predicate='"x-resp-deny" in request.headers',
        with_status=418,
        with_headers='[["x-deny-phase", "response"]]',
        with_body="Teapot response",
    )
    return pipeline_policy


def test_path_based_deny(client):
    """Request to a path matching the deny predicate is denied with 403."""
    response = client.get("/deny-path")
    assert response.status_code == 403


def test_cel_predicate_does_not_deny(client):
    """Request to a path not matching any deny predicate passes through."""
    response = client.get("/get")
    assert response.status_code == 200


def test_header_based_deny(client):
    """Request with a header matching the deny predicate is denied."""
    response = client.get("/get", headers={"x-deny-me": "true"})
    assert response.status_code == 401


def test_header_based_deny_absent(client):
    """Request without the blocked header passes through."""
    response = client.get("/get")
    assert response.status_code == 200


def test_multiple_deny_actions_or_behavior(client):
    """Multiple deny actions behave as OR: any matching predicate denies the request."""
    assert client.get("/deny-path").status_code == 403
    assert client.get("/get", headers={"x-deny-me": "true"}).status_code == 401
    assert client.get("/get").status_code == 200


def test_deny_custom_status_code(client):
    """Deny with custom withStatus returns that status code."""
    response = client.get("/custom-status")
    assert response.status_code == 429


def test_deny_custom_headers(client):
    """Deny with withHeaders includes custom headers in the denied response."""
    response = client.get("/custom-headers")
    assert response.status_code == 403
    assert response.headers.get("x-deny-reason") == "blocked"


def test_deny_custom_body(client):
    """Deny with withBody returns custom body text."""
    response = client.get("/custom-body")
    assert response.status_code == 403
    assert response.text == "Access denied"


def test_deny_all_response_fields(client):
    """Deny with withStatus, withHeaders, and withBody all set returns all fields."""
    response = client.get("/custom-all")
    assert response.status_code == 451
    assert response.headers.get("x-deny-reason") == "full-custom"
    assert response.text == "Fully customized denial"


def test_response_deny_override_status(client):
    """Response deny overrides the backend response status code."""
    response = client.get("/get", headers={"x-override-code": "true"})
    assert response.status_code == 503


def test_response_deny_no_override(client):
    """Response without the override header passes through normally."""
    response = client.get("/get")
    assert response.status_code == 200


def test_response_deny_with_headers_and_body(client):
    """Response deny with all fields replaces the backend response."""
    response = client.get("/get", headers={"x-resp-deny": "true"})
    assert response.status_code == 418
    assert response.headers.get("x-deny-phase") == "response"
    assert response.text == "Teapot response"
