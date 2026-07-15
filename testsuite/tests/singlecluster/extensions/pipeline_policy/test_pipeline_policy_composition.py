"""Tests for PipelinePolicy composition: action ordering, empty and partial pipelines."""

import pytest

from testsuite.kuadrant.extensions.pipeline_policy import PipelinePolicy

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module", autouse=True)
def commit():
    """No module-level policy; each test creates its own."""


def test_first_deny_wins(request, cluster, blame, route, client, module_label):
    """First deny action terminates the chain; the second deny with the same predicate never executes."""
    policy = PipelinePolicy.create_instance(cluster, blame("order"), route, labels={"testRun": module_label})
    policy.on_http_request.add_deny(predicate='request.url_path == "/order-test"', with_status=403)
    policy.on_http_request.add_deny(predicate='request.url_path == "/order-test"', with_status=429)
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/order-test")
    assert response.status_code == 403


def test_response_action_ordering(request, cluster, blame, route, client, module_label):
    """Response actions execute in spec order; both headers from separate actions are present."""
    policy = PipelinePolicy.create_instance(cluster, blame("respord"), route, labels={"testRun": module_label})
    policy.on_http_response.add_headers([["x-first", "alpha"]])
    policy.on_http_response.add_headers([["x-second", "bravo"]])
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-first") == "alpha"
    assert response.headers.get("x-second") == "bravo"


def test_empty_pipeline(request, cluster, blame, route, client, module_label):
    """PipelinePolicy with no actions passes requests through unmodified."""
    policy = PipelinePolicy.create_instance(cluster, blame("empty"), route, labels={"testRun": module_label})
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-pipeline-policy") is None


def test_request_only_pipeline(request, cluster, blame, route, client, module_label):
    """PipelinePolicy with only request actions and no response section works correctly."""
    policy = PipelinePolicy.create_instance(cluster, blame("reqonly"), route, labels={"testRun": module_label})
    policy.on_http_request.add_deny(predicate='request.url_path == "/blocked"', with_status=403)
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    assert client.get("/get").status_code == 200
    assert client.get("/blocked").status_code == 403


def test_response_only_pipeline(request, cluster, blame, route, client, module_label):
    """PipelinePolicy with only response actions and no request section works correctly."""
    policy = PipelinePolicy.create_instance(cluster, blame("resonly"), route, labels={"testRun": module_label})
    policy.on_http_response.add_headers([["x-resp-only", "true"]])
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-resp-only") == "true"
