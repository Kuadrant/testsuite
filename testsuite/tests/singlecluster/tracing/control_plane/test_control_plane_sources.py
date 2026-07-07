"""
Control plane tracing tests for source policies attributes.

Tests verify that reconciliation spans include 'sources' attributes
linking them to the policies that triggered the reconciliation.
"""

import time

import pytest

from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy
from testsuite.kubernetes import Selector

pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def authconfig_trace(auth_traces):
    """Find trace with authconfig span that has sources attribute"""
    for trace in auth_traces:
        spans = trace.filter_spans(lambda s: s.operation_name == "authconfig" and s.has_tag("sources"))
        if spans:
            return trace

    pytest.fail("No trace with authconfig span containing 'sources' attribute found")
    return None


@pytest.fixture(scope="module")
def limitador_trace(rl_traces):
    """Find trace with limitador limits span that has sources attribute"""
    for trace in rl_traces:
        spans = trace.filter_spans(lambda s: s.operation_name == "reconciler.limitador_limits" and s.has_tag("sources"))
        if spans:
            return trace

    pytest.fail("No trace with limits span containing 'sources' attribute found")
    return None


def test_authconfig_span_attributes(authconfig_trace, authorization):
    """
    Validate that authconfig reconciliation spans include sources, name, and namespace attributes.
    """
    policy_ref = f"authpolicy.kuadrant.io:{authorization.namespace()}/{authorization.name()}"
    authconfig_spans = authconfig_trace.filter_spans(
        lambda s: s.operation_name == "authconfig"
        and s.has_tag("sources")
        and policy_ref in (s.get_tag("sources") or [])
    )
    assert authconfig_spans, f"AuthPolicy {policy_ref} not found in any authconfig span sources"
    authconfig_span = authconfig_spans[0]

    assert authconfig_span.has_tag("name"), "authconfig span missing 'name' attribute"
    assert authconfig_span.has_tag("namespace"), "authconfig span missing 'namespace' attribute"

    name = authconfig_span.get_tag("name")
    namespace = authconfig_span.get_tag("namespace")
    assert name is not None and name != "", "authconfig name attribute is empty"
    assert namespace is not None and namespace != "", "authconfig namespace attribute is empty"


def test_limitador_span_attributes(limitador_trace, rate_limit):
    """
    Validate that limitador limits reconciliation spans include sources, name, and namespace attributes.
    """
    policy_ref = f"ratelimitpolicy.kuadrant.io:{rate_limit.namespace()}/{rate_limit.name()}"
    limitador_spans = limitador_trace.filter_spans(
        lambda s: s.operation_name == "reconciler.limitador_limits"
        and s.has_tag("sources")
        and policy_ref in (s.get_tag("sources") or [])
    )
    assert limitador_spans, f"RateLimitPolicy {policy_ref} not found in any limitador span sources"
    limitador_span = limitador_spans[0]

    assert limitador_span.has_tag("name"), "limitador span missing 'name' attribute"
    assert limitador_span.has_tag("namespace"), "limitador span missing 'namespace' attribute"

    name = limitador_span.get_tag("name")
    namespace = limitador_span.get_tag("namespace")
    assert name is not None and name != "", "limitador name attribute is empty"
    assert namespace is not None and namespace != "", "limitador namespace attribute is empty"


def test_authconfig_span_is_child_of_reconciler(authconfig_trace):
    """
    Validate that authconfig spans are children of reconciler.auth_configs spans.
    """
    authconfig_span = authconfig_trace.filter_spans(
        lambda s: s.operation_name == "authconfig" and s.has_tag("sources")
    )[0]

    parent_id = authconfig_span.get_parent_id()
    assert parent_id is not None, "authconfig span has no parent"

    parent_span = authconfig_trace.get_span_by_id(parent_id)
    assert parent_span is not None, f"Parent span with ID {parent_id} not found in trace"
    assert (
        parent_span.operation_name == "reconciler.auth_configs"
    ), f"Expected parent to be 'reconciler.auth_configs' but got '{parent_span.operation_name}'"


@pytest.fixture(scope="function")
def second_auth_policy(request, cluster, blame, route, module_label):
    """Create a second AuthPolicy targeting the same route"""
    create_time = int(time.time() * 1_000_000)
    second_policy = AuthPolicy.create_instance(cluster, blame("second-auth"), route, labels={"app": module_label})
    second_policy.identity.add_api_key("second_key", Selector(matchLabels={"app": module_label}))
    request.addfinalizer(second_policy.delete)
    second_policy.commit()
    second_policy.wait_for_ready()
    return second_policy, create_time


def test_authconfig_sources_contains_multiple_policies(authorization, second_auth_policy, tracing):
    """
    Validate that when multiple AuthPolicies target the same route,
    both policy references appear in authconfig span sources across traces.
    """
    second_policy, create_time = second_auth_policy

    first_policy_ref = f"authpolicy.kuadrant.io:{authorization.namespace()}/{authorization.name()}"
    second_policy_ref = f"authpolicy.kuadrant.io:{second_policy.namespace()}/{second_policy.name()}"

    all_traces = tracing.get_traces(service="kuadrant-operator")
    all_sources = set()
    for trace in all_traces:
        for span in trace.filter_spans(lambda s: s.operation_name == "authconfig" and s.has_tag("sources")):
            sources = span.get_tag("sources")
            if sources:
                all_sources.update(sources)
    assert first_policy_ref in all_sources, f"First policy {first_policy_ref} not found in any authconfig span sources"

    scoped_traces = tracing.get_traces(service="kuadrant-operator", start_time=create_time)
    scoped_sources = set()
    for trace in scoped_traces:
        for span in trace.filter_spans(lambda s: s.operation_name == "authconfig" and s.has_tag("sources")):
            sources = span.get_tag("sources")
            if sources:
                scoped_sources.update(sources)
    assert (
        second_policy_ref in scoped_sources
    ), f"Second policy {second_policy_ref} not found in any authconfig span sources"


@pytest.fixture(scope="function")
def second_rate_limit_policy(request, cluster, blame, route, module_label):
    """Create a second RateLimitPolicy targeting the same route"""
    create_time = int(time.time() * 1_000_000)
    second_policy = RateLimitPolicy.create_instance(cluster, blame("second-rlp"), route, labels={"app": module_label})
    second_policy.add_limit("basic", [Limit(10, "10s")])
    request.addfinalizer(second_policy.delete)
    second_policy.commit()
    second_policy.wait_for_ready()
    return second_policy, create_time


def test_limitador_sources_contains_multiple_policies(rate_limit, second_rate_limit_policy, tracing):
    """
    Validate that when multiple RateLimitPolicies target the same route,
    both policy references appear in limitador span sources across traces.
    """
    second_policy, create_time = second_rate_limit_policy

    first_policy_ref = f"ratelimitpolicy.kuadrant.io:{rate_limit.namespace()}/{rate_limit.name()}"
    second_policy_ref = f"ratelimitpolicy.kuadrant.io:{second_policy.namespace()}/{second_policy.name()}"

    all_traces = tracing.get_traces(service="kuadrant-operator")
    all_sources = set()
    for trace in all_traces:
        for span in trace.filter_spans(
            lambda s: s.operation_name == "reconciler.limitador_limits" and s.has_tag("sources")
        ):
            sources = span.get_tag("sources")
            if sources:
                all_sources.update(sources)
    assert first_policy_ref in all_sources, f"First policy {first_policy_ref} not found in any limitador span sources"

    scoped_traces = tracing.get_traces(service="kuadrant-operator", start_time=create_time)
    scoped_sources = set()
    for trace in scoped_traces:
        for span in trace.filter_spans(
            lambda s: s.operation_name == "reconciler.limitador_limits" and s.has_tag("sources")
        ):
            sources = span.get_tag("sources")
            if sources:
                scoped_sources.update(sources)
    assert (
        second_policy_ref in scoped_sources
    ), f"Second policy {second_policy_ref} not found in any limitador span sources"
