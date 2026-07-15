"""Tests for PipelinePolicy validation: rejected configurations and error conditions."""

import pytest

from testsuite.gateway import CustomReference
from testsuite.kuadrant.extensions.pipeline_policy import PipelinePolicy
from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module", autouse=True)
def commit():
    """No module-level policy; each test creates its own with bad configuration."""


@pytest.mark.parametrize("kind", ["HTTPRoute", "Gateway"])
def test_invalid_target_ref(request, cluster, blame, kind, module_label):
    """PipelinePolicy targeting a non-existent resource does not reach Accepted state."""
    target_name = "does-not-exist"
    target = CustomReference(
        group="gateway.networking.k8s.io",
        kind=kind,
        name=target_name,
    )
    policy = PipelinePolicy.create_instance(cluster, blame("bad-target"), target, labels={"testRun": module_label})
    policy.on_http_request.add_deny(predicate='request.url_path == "/blocked"', with_status=403)

    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", message=f"targetRef {kind} {cluster.project}/{target_name} not found"),
        timelimit=30,
    ), f"Policy did not report target not found, status: {policy.refresh().model.status.conditions}"


def test_top_level_fail_action(request, cluster, blame, route, module_label):
    """PipelinePolicy with a top-level fail action (not inside gRPC onReply) should not be accepted."""
    policy = PipelinePolicy.create_instance(cluster, blame("top-fail"), route, labels={"testRun": module_label})
    policy.on_http_request.add_fail("top-level fail", predicate='request.url_path == "/fail"')

    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", message="fail action must reference a gRPC response variable"),
        timelimit=30,
    ), f"Policy with top-level fail was accepted, status: {policy.refresh().model.status.conditions}"


def test_invalid_cel_expression(request, cluster, blame, route, module_label):
    """PipelinePolicy with malformed CEL predicate fails to enforce."""
    policy = PipelinePolicy.create_instance(cluster, blame("bad-cel"), route, labels={"testRun": module_label})
    policy.on_http_request.add_deny(predicate="INVALID CEL !!!", with_status=403)

    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", message="invalid CEL expression"),
        timelimit=30,
    ), f"Policy did not report error for invalid CEL, status: {policy.refresh().model.status.conditions}"


def test_variable_forward_reference(request, cluster, blame, route, module_label):
    """PipelinePolicy referencing a variable before it is defined should fail validation."""
    var_name = "threatResponse"
    policy = PipelinePolicy.create_instance(cluster, blame("fwd-ref"), route, labels={"testRun": module_label})
    policy.on_http_request.add_deny(predicate=f"{var_name}.threat_level >= 50", with_status=403)
    policy.on_http_request.add_grpc_method(method="nonexistent-method", var=var_name)

    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", message=f'action references variable "{var_name}" before it is populated'),
        timelimit=60,
    ), f"Policy did not reject forward reference, status: {policy.refresh().model.status.conditions}"


def test_duplicate_variable_name(request, cluster, blame, route, module_label):
    """PipelinePolicy with two gRPC methods using the same variable name should fail validation."""
    var_name = "dupVar"
    policy = PipelinePolicy.create_instance(cluster, blame("dup-var"), route, labels={"testRun": module_label})
    policy.on_http_request.add_grpc_method(method="method-a", var=var_name)
    policy.on_http_request.add_grpc_method(method="method-b", var=var_name)

    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", message=f'duplicate variable name "{var_name}"'),
        timelimit=60,
    ), f"Policy did not reject duplicate var, status: {policy.refresh().model.status.conditions}"
