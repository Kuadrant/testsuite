"""Tests for PipelinePolicy lifecycle: update and delete."""

import time

import pytest

from testsuite.kuadrant.extensions.pipeline_policy import PipelinePolicy
from testsuite.utils.constants import EXTENSION_POLICY_PROPAGATION_WAIT

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module", autouse=True)
def commit():
    """No module-level policy; each test creates its own."""


@pytest.mark.flaky(reruns=0)
def test_update_policy(request, cluster, blame, route, client, module_label):
    """Adding a new response header via policy update propagates to traffic."""
    policy = PipelinePolicy.create_instance(cluster, blame("upd-pp"), route, labels={"testRun": module_label})
    policy.on_http_response.add_headers([["x-update-test", "active"]])
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-update-test") == "active"
    assert response.headers.get("x-update-new") is None

    policy.on_http_response.add_headers([["x-update-new", "true"]])
    policy.wait_for_ready()

    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-update-test") == "active"
    assert response.headers.get("x-update-new") == "true"


@pytest.mark.flaky(reruns=0)
def test_delete_policy(request, cluster, blame, route, client, module_label):
    """After deleting the PipelinePolicy, the CR is removed and the actions stop being enforced."""
    policy = PipelinePolicy.create_instance(cluster, blame("del-pp"), route, labels={"testRun": module_label})
    policy.on_http_response.add_headers([["x-delete-test", "active"]])
    request.addfinalizer(policy.delete)
    policy.commit()
    policy.wait_for_ready()

    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-delete-test") == "active"

    policy.delete()
    assert not policy.committed, "PipelinePolicy was not deleted"
    time.sleep(EXTENSION_POLICY_PROPAGATION_WAIT)

    response = client.get("/get")
    assert response.status_code == 200
    assert response.headers.get("x-delete-test") is None
