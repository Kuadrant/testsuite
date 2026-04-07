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
def authconfig_trace(auth_traces, skip_or_fail):
    """Find trace with authconfig span that has sources attribute"""
    for trace in auth_traces:
        spans = trace.filter_spans(lambda s: s.operation_name == "authconfig" and s.has_tag("sources"))
        if spans:
            return trace

    skip_or_fail("No trace with authconfig span containing 'sources' attribute found")


@pytest.fixture(scope="module")
def limitador_trace(rl_traces, skip_or_fail):
    """Find trace with span that has sources attribute"""
    for trace in rl_traces:
        spans = trace.filter_spans(lambda s: s.operation_name == "limits" and s.has_tag("sources"))
        if spans:
            return trace

    available_operations = list({span.operation_name for trace in rl_traces for span in trace.spans})[:20]
    skip_or_fail(
        f"No trace with spans containing 'sources' attribute found in rate limit traces. "
        f"Available operations: {available_operations}"
    )


def test_authconfig_span_attributes(authconfig_trace, authorization):
    """
    Validate that authconfig reconciliation spans include sources, name, and namespace attributes.
    """
    authconfig_span = authconfig_trace.filter_spans(
        lambda s: s.operation_name == "authconfig" and s.has_tag("sources")
    )[0]

    sources = authconfig_span.get_tag("sources")
    assert sources is not None, "sources attribute is None"
    assert len(sources) > 0, "sources list is empty"

    policy_ref = f"authpolicy.kuadrant.io:{authorization.namespace()}/{authorization.name()}"
    assert policy_ref in sources, f"AuthPolicy {policy_ref} not found in sources: {sources}"

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
    limitador_span = limitador_trace.filter_spans(lambda s: s.has_tag("sources"))[0]

    sources = limitador_span.get_tag("sources")
    assert sources is not None, "sources attribute is None"
    assert len(sources) > 0, "sources list is empty"

    policy_ref = f"ratelimitpolicy.kuadrant.io:{rate_limit.namespace()}/{rate_limit.name()}"
    assert policy_ref in sources, f"RateLimitPolicy {policy_ref} not found in sources: {sources}"

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
    # Capture timestamp before creating the second policy
    create_time = int(time.time() * 1_000_000)

    second_policy = AuthPolicy.create_instance(cluster, blame("second-auth"), route, labels={"app": module_label})
    second_policy.identity.add_api_key("second_key", Selector(matchLabels={"app": module_label}))
    request.addfinalizer(second_policy.delete)
    second_policy.commit()
    second_policy.wait_for_ready()
    return second_policy, create_time


@pytest.fixture(scope="function")
def authconfig_trace_multiple_policies(authorization, second_auth_policy, tracing, skip_or_fail):
    """Find trace with authconfig span containing sources from multiple policies"""
    second_policy, create_time = second_auth_policy

    # Query for traces that started after the second policy was created
    # The backoff decorator will retry until traces appear
    traces = tracing.get_traces(service="kuadrant-operator", start_time=create_time)

    # Look for a trace that has authconfig span with at least one policy in sources
    first_policy_ref = f"authpolicy.kuadrant.io:{authorization.namespace()}/{authorization.name()}"
    second_policy_ref = f"authpolicy.kuadrant.io:{second_policy.namespace()}/{second_policy.name()}"

    for trace in traces:
        spans = trace.filter_spans(lambda s: s.operation_name == "authconfig" and s.has_tag("sources"))
        for span in spans:
            sources = span.get_tag("sources")
            if sources and (first_policy_ref in sources or second_policy_ref in sources):
                return trace

    skip_or_fail(
        f"No trace with authconfig span found with either policy. "
        f"Looking for {first_policy_ref} or {second_policy_ref} in sources"
    )


def test_authconfig_sources_contains_multiple_policies(
    authconfig_trace_multiple_policies, authorization, second_auth_policy
):
    """
    Validate that when multiple AuthPolicies target the same route,
    the authconfig span's sources attribute contains at least one of them.
    """
    second_policy, _ = second_auth_policy

    authconfig_spans = authconfig_trace_multiple_policies.filter_spans(
        lambda s: s.operation_name == "authconfig" and s.has_tag("sources")
    )

    assert len(authconfig_spans) > 0, "No authconfig spans with sources found"

    first_policy_ref = f"authpolicy.kuadrant.io:{authorization.namespace()}/{authorization.name()}"
    second_policy_ref = f"authpolicy.kuadrant.io:{second_policy.namespace()}/{second_policy.name()}"

    # Check all authconfig spans with sources to find one with our policies
    found = False
    for span in authconfig_spans:
        sources = span.get_tag("sources")
        assert len(sources) > 0, f"sources list is empty for span {span.span_id}"

        if first_policy_ref in sources or second_policy_ref in sources:
            found = True
            break

    assert found, (
        f"Neither {first_policy_ref} nor {second_policy_ref} found in any authconfig span sources. "
        f"Checked {len(authconfig_spans)} span(s)"
    )


@pytest.fixture(scope="function")
def second_rate_limit_policy(request, cluster, blame, route, module_label):
    """Create a second RateLimitPolicy targeting the same route"""
    # Capture timestamp before creating the second policy
    create_time = int(time.time() * 1_000_000)

    second_policy = RateLimitPolicy.create_instance(cluster, blame("second-rlp"), route, labels={"app": module_label})
    second_policy.add_limit("basic", [Limit(10, "10s")])
    request.addfinalizer(second_policy.delete)
    second_policy.commit()
    second_policy.wait_for_ready()
    return second_policy, create_time


@pytest.fixture(scope="function")
def limitador_trace_multiple_policies(rate_limit, second_rate_limit_policy, tracing, skip_or_fail):
    """Find trace with span containing sources from multiple rate limit policies"""
    second_policy, create_time = second_rate_limit_policy

    # Query for traces that started after the second policy was created
    # The backoff decorator will retry until traces appear
    traces = tracing.get_traces(service="kuadrant-operator", start_time=create_time)

    # Look for a trace that has span with at least one policy in sources
    first_policy_ref = f"ratelimitpolicy.kuadrant.io:{rate_limit.namespace()}/{rate_limit.name()}"
    second_policy_ref = f"ratelimitpolicy.kuadrant.io:{second_policy.namespace()}/{second_policy.name()}"

    for trace in traces:
        spans = trace.filter_spans(lambda s: s.has_tag("sources"))
        for span in spans:
            sources = span.get_tag("sources")
            if sources and (first_policy_ref in sources or second_policy_ref in sources):
                return trace

    skip_or_fail(f"No trace found with either policy. Looking for {first_policy_ref} or {second_policy_ref} in sources")


def test_limitador_sources_contains_multiple_policies(
    limitador_trace_multiple_policies, rate_limit, second_rate_limit_policy
):
    """
    Validate that when multiple RateLimitPolicies target the same route,
    the limitador limits span's sources attribute contains at least one of them.
    """
    second_policy, _ = second_rate_limit_policy

    spans_with_sources = limitador_trace_multiple_policies.filter_spans(lambda s: s.has_tag("sources"))

    assert len(spans_with_sources) > 0, "No spans with sources found"

    first_policy_ref = f"ratelimitpolicy.kuadrant.io:{rate_limit.namespace()}/{rate_limit.name()}"
    second_policy_ref = f"ratelimitpolicy.kuadrant.io:{second_policy.namespace()}/{second_policy.name()}"

    # Check all spans with sources to find one with our policies
    found = False
    for span in spans_with_sources:
        sources = span.get_tag("sources")
        assert len(sources) > 0, f"sources list is empty for span {span.span_id}"

        if first_policy_ref in sources or second_policy_ref in sources:
            found = True
            break

    assert found, (
        f"Neither {first_policy_ref} nor {second_policy_ref} found in any span sources. "
        f"Checked {len(spans_with_sources)} span(s)"
    )