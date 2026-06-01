"""Tests for PipelinePolicy response add_headers actions."""

import pytest

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module")
def pipeline_policy(pipeline_policy):
    """PipelinePolicy with various add_headers response actions for testing."""
    pipeline_policy.add_response_headers([["x-single", "one"]])
    pipeline_policy.add_response_headers([["x-multi-a", "alpha"], ["x-multi-b", "bravo"]])
    pipeline_policy.add_response_headers([["x-separate", "separate-value"]])

    pipeline_policy.add_response_headers(
        [["x-conditional", "present"]],
        predicate='"x-trigger" in request.headers',
    )

    pipeline_policy.add_response_headers(
        [["x-mode", "active"]],
        predicate='"x-trigger" in request.headers',
    )
    pipeline_policy.add_response_headers(
        [["x-mode", "inactive"]],
        predicate='!("x-trigger" in request.headers)',
    )

    return pipeline_policy


def test_single_response_header(client):
    """Single response header is added to the response."""
    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-single") == "one"


def test_multiple_headers_in_one_action(client):
    """Multiple headers added in a single add_headers action are all present."""
    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-multi-a") == "alpha"
    assert response.headers.get("x-multi-b") == "bravo"


def test_separate_add_headers_actions(client):
    """Headers from two separate add_headers actions are all present."""
    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-single") == "one"
    assert response.headers.get("x-separate") == "separate-value"


def test_conditional_header_present(client):
    """Header with predicate is added when the condition is met."""
    response = client.get("/get", headers={"x-trigger": "true"})
    assert response.status_code == 200
    assert response.headers.get("x-conditional") == "present"


def test_conditional_header_absent(client):
    """Header with predicate is not added when the condition is not met."""
    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-conditional") is None


def test_mutually_exclusive_headers_active(client):
    """Mutually exclusive headers: active mode when trigger header is present."""
    response = client.get("/get", headers={"x-trigger": "true"})
    assert response.status_code == 200
    assert response.headers.get("x-mode") == "active"


def test_mutually_exclusive_headers_inactive(client):
    """Mutually exclusive headers: inactive mode when trigger header is absent."""
    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-mode") == "inactive"
