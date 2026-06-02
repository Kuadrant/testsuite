"""Tests for PipelinePolicy validation: rejected configurations and error conditions."""

import pytest

from testsuite.gateway import CustomReference
from testsuite.kuadrant.extensions.pipeline_policy import PipelinePolicy
from testsuite.kuadrant.policy import has_condition

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.extensions]


@pytest.fixture(scope="module", autouse=True)
def commit():
    """No module-level policy; each test creates its own with bad configuration."""


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/2022")
@pytest.mark.xfail(reason="https://github.com/Kuadrant/kuadrant-operator/issues/2022")
def test_invalid_target_ref(request, cluster, blame):
    """PipelinePolicy targeting a non-existent HTTPRoute does not reach Enforced state."""
    target = CustomReference(
        group="gateway.networking.k8s.io",
        kind="HTTPRoute",
        name="does-not-exist",
    )
    policy = PipelinePolicy.create_instance(cluster, blame("bad-target"), target)
    policy.on_http_request.add_deny(predicate='request.url_path == "/blocked"', with_status=403)

    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", "TargetNotFound"),
        timelimit=30,
    ), f"Policy did not report TargetNotFound, status: {policy.refresh().model.status.conditions}"


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/2022")
@pytest.mark.xfail(reason="https://github.com/Kuadrant/kuadrant-operator/issues/2022")
def test_invalid_gateway_target_ref(request, cluster, blame):
    """PipelinePolicy targeting a non-existent Gateway does not reach Enforced state."""
    target = CustomReference(
        group="gateway.networking.k8s.io",
        kind="Gateway",
        name="does-not-exist",
    )
    policy = PipelinePolicy.create_instance(cluster, blame("bad-gw"), target)
    policy.on_http_request.add_deny(predicate='request.url_path == "/blocked"', with_status=403)

    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", "TargetNotFound"),
        timelimit=30,
    ), f"Policy did not report TargetNotFound, status: {policy.refresh().model.status.conditions}"


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/2015")
@pytest.mark.xfail(reason="https://github.com/Kuadrant/kuadrant-operator/issues/2015")
def test_top_level_fail_action(request, cluster, blame, route):
    """PipelinePolicy with a top-level fail action (not inside gRPC onReply) should not be accepted."""
    policy = PipelinePolicy.create_instance(cluster, blame("top-fail"), route)
    policy.on_http_request.add_fail("top-level fail", predicate='request.url_path == "/fail"')

    request.addfinalizer(policy.delete)
    policy.commit()

    # TODO: add expected message assertion once the validation is implemented
    assert policy.wait_until(
        has_condition("Accepted", "False"),
        timelimit=30,
    ), f"Policy with top-level fail was accepted, status: {policy.refresh().model.status.conditions}"


def test_invalid_cel_expression(request, cluster, blame, route):
    """PipelinePolicy with malformed CEL predicate fails to enforce."""
    policy = PipelinePolicy.create_instance(cluster, blame("bad-cel"), route)
    policy.on_http_request.add_deny(predicate="INVALID CEL !!!", with_status=403)

    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", message="invalid CEL expression"),
        timelimit=30,
    ), f"Policy did not report error for invalid CEL, status: {policy.refresh().model.status.conditions}"


def test_variable_forward_reference(request, cluster, blame, route):
    """PipelinePolicy referencing a variable before it is defined should fail validation."""
    var_name = "threatResponse"
    policy = PipelinePolicy.create_instance(cluster, blame("fwd-ref"), route)
    policy.on_http_request.add_deny(predicate=f"{var_name}.threat_level >= 50", with_status=403)
    policy.on_http_request.add_grpc_method(method="nonexistent-method", var=var_name)

    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", message=f'action references variable "{var_name}" before it is populated'),
        timelimit=60,
    ), f"Policy did not reject forward reference, status: {policy.refresh().model.status.conditions}"


def test_duplicate_variable_name(request, cluster, blame, route):
    """PipelinePolicy with two gRPC methods using the same variable name should fail validation."""
    var_name = "dupVar"
    policy = PipelinePolicy.create_instance(cluster, blame("dup-var"), route)
    policy.on_http_request.add_grpc_method(method="method-a", var=var_name)
    policy.on_http_request.add_grpc_method(method="method-b", var=var_name)

    request.addfinalizer(policy.delete)
    policy.commit()

    assert policy.wait_until(
        has_condition("Accepted", "False", message=f'duplicate variable name "{var_name}"'),
        timelimit=60,
    ), f"Policy did not reject duplicate var, status: {policy.refresh().model.status.conditions}"
