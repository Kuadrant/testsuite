"""
Error and edge case tracing tests.

Tests validation failures, orphaned policies, and error handling in control plane traces.
"""

import pytest

from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kubernetes import Selector

pytestmark = [pytest.mark.observability, pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]

# Expected exception types for orphaned policy scenarios
EXPECTED_ORPHAN_EXCEPTION_TYPE = "github.com/kuadrant/kuadrant-operator/internal/kuadrant.ErrPolicyTargetNotFound"


@pytest.fixture(scope="function")
def orphan_test_route(request, cluster, blame, gateway, module_label, backend):
    """Route for orphaned policy testing"""
    orphan_route = HTTPRoute.create_instance(cluster, blame("orphan-route"), gateway, {"app": module_label})
    orphan_route.add_backend(backend)
    request.addfinalizer(orphan_route.delete)
    orphan_route.commit()
    return orphan_route


@pytest.fixture(scope="function")
def orphan_test_policy(request, cluster, blame, orphan_test_route, module_label):
    """Policy for orphaned testing - will be cleaned up"""
    orphan_policy = AuthPolicy.create_instance(cluster, blame("orphan-policy"), orphan_test_route)
    orphan_policy.identity.add_api_key("orphan_key", Selector(matchLabels={"app": module_label}))
    request.addfinalizer(orphan_policy.delete)
    orphan_policy.commit()
    orphan_policy.wait_for_ready()
    return orphan_policy


@pytest.mark.flaky(reruns=0)
def test_orphaned_policy_reconciliation_traced(orphan_test_route, orphan_test_policy, tracing):
    """
    Validate traces when policy references deleted resources
    """
    # Delete the route (orphaning the policy)
    orphan_test_route.delete()
    orphan_test_route.wait_until(lambda obj: not obj.exists(), timelimit=30)

    # Look for traces with error indicators or warnings
    policy_traces = tracing.get_traces(
        service="kuadrant-operator", tags={"policy.name": orphan_test_policy.name(), "error": "true"}
    )

    # Check if any spans indicate problems (error status or exception in logs)
    error_spans = []
    for trace in policy_traces:
        error_spans.extend(
            trace.filter_spans(
                lambda s: s.has_log_field("exception.type", EXPECTED_ORPHAN_EXCEPTION_TYPE)
                and s.has_log_field("event", "exception")
                and s.has_log_field("exception.message", f"AuthPolicy target {orphan_test_route.name()} was not found")
            )
        )

    assert len(error_spans) > 0, f"Should have spans with exception.type={EXPECTED_ORPHAN_EXCEPTION_TYPE}"
