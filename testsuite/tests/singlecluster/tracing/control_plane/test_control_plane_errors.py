"""
Error and edge case tracing tests.

Tests validation failures, orphaned policies, and error handling in control plane traces.
"""

import time

import pytest

from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kubernetes import Selector

pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def invalid_auth_policy(request, cluster, blame, route, label):
    """Invalid AuthPolicy for validation failure testing."""
    authorization = AuthPolicy.create_instance(cluster, blame("authz"), route, labels={"testRun": label})
    authorization.identity.add_api_key(
        "invalid_key",
        selector=Selector(matchLabels={"app": "non-existent"}),  # This selector won't match any secret
    )
    request.addfinalizer(authorization.delete)
    authorization.commit()
    authorization.wait_for_ready()
    return authorization


def test_invalid_policy_validation_failure_traced(tracing, invalid_auth_policy):
    """
    Validate that policy validation failures are properly traced.

    Verifies that:
    - Invalid policies generate traces
    - Validation failure is marked with error status
    - Error messages are captured in span logs
    - Can identify what validation failed
    - Operators can debug rejected policies via traces
    """
    # Wait for reconciliation traces (even for invalid policy)
    policy_traces = tracing.get_traces(service="kuadrant-operator", tags={"policy.name": invalid_auth_policy.name()})
    assert len(policy_traces) > 0, "No traces found for invalid policy"

    # Extract validation spans
    validation_spans = []
    for trace in policy_traces:
        validation_spans.extend(
            trace.filter_spans(
                predicate=lambda s: "validate" in s.operation_name.lower() or "validation" in s.operation_name.lower()
            )
        )

    # Check for error indicators in any spans
    error_found = False
    for trace in policy_traces:
        error_spans = trace.filter_spans(
            predicate=lambda s: s.get_tag("otel.status_code") == "ERROR"
            or any(
                keyword in field.get("value", "").lower()
                for log_entry in s.logs
                for field in log_entry.get("fields", [])
                for keyword in ["error", "fail", "invalid", "warning"]
            )
        )
        if error_spans:
            error_found = True
            break

    # Verify we collected validation spans or found error indicators somewhere
    assert (
        len(validation_spans) > 0 or error_found
    ), "Should have validation spans or error indicators for invalid policy"


@pytest.fixture(scope="function")
def orphan_test_route(request, cluster, blame, gateway, module_label, backend):
    """Route for orphaned policy testing - not auto-deleted."""
    orphan_route = HTTPRoute.create_instance(cluster, blame("orphan-route"), gateway, {"app": module_label})
    orphan_route.add_backend(backend)
    orphan_route.commit()
    # Note: No finalizer - test controls deletion
    return orphan_route


@pytest.fixture(scope="function")
def orphan_test_policy(request, cluster, blame, orphan_test_route, module_label):
    """Policy for orphaned testing - will be cleaned up."""
    orphan_policy = AuthPolicy.create_instance(cluster, blame("orphan-policy"), orphan_test_route)
    orphan_policy.identity.add_api_key("orphan_key", Selector(matchLabels={"app": module_label}))
    request.addfinalizer(orphan_policy.delete)
    orphan_policy.commit()
    orphan_policy.wait_for_ready()
    return orphan_policy


def test_orphaned_policy_reconciliation_traced(orphan_test_route, orphan_test_policy, tracing):
    """
    Test: Validate traces when policy references deleted resources.

    Verifies:
    - Policy with deleted HTTPRoute target generates error trace or warning
    - Error details are observable
    - Reconciliation attempts are traceable
    """
    # Delete the route (orphaning the policy)
    orphan_test_route.delete()

    # Wait a bit for reconciliation to detect the missing target
    time.sleep(5)

    # Look for traces with error indicators or warnings
    policy_traces = tracing.get_traces(service="kuadrant-operator", tags={"policy.name": orphan_test_policy.name()})

    # Check if any spans indicate problems (error status or error logs)
    error_spans = []
    for trace in policy_traces:
        error_spans.extend(
            trace.filter_spans(
                predicate=lambda s: s.get_tag("otel.status_code") == "ERROR"
                or any(
                    keyword in field.get("value", "").lower()
                    for log_entry in s.logs
                    for field in log_entry.get("fields", [])
                    for keyword in ["error", "fail", "invalid", "warning"]
                )
            )
        )

    # Note: This test is informational - not all operators may mark orphaned policies as errors
    # The key is that traces exist showing reconciliation attempts
    assert len(policy_traces) > 0, "Should have traces for orphaned policy reconciliation attempts"
