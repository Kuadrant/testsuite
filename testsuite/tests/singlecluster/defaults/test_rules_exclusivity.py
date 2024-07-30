"""Test mutual exclusivity of defaults block and implicit defaults"""

import pytest
from openshift_client import OpenShiftPythonException

from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def commit():
    """We need to try to commit objects during the actual test"""
    return None


def test_rules_exclusivity_authorization(cluster, route, oidc_provider, module_label, blame):
    """Test that server will reject object with implicit and explicit defaults defined simultaneously in AuthPolicy"""
    authorization = AuthPolicy.create_instance(cluster, blame("authz"), route, labels={"testRun": module_label})
    authorization.defaults.identity.add_oidc("inside-defaults", oidc_provider.well_known["issuer"])
    authorization.identity.add_oidc("outside-defaults", oidc_provider.well_known["issuer"])

    with pytest.raises(OpenShiftPythonException, match="Implicit and explicit defaults are mutually exclusive"):
        authorization.commit()


def test_rules_exclusivity_rate_limit(cluster, route, module_label, blame):
    """Test that server will reject object with implicit and explicit defaults simultaneously in RateLimitPolicy"""
    rate_limit = RateLimitPolicy.create_instance(cluster, blame("limit"), route, labels={"testRun": module_label})
    rate_limit.defaults.add_limit("inside-defaults", [Limit(2, 5)])
    rate_limit.add_limit("outside-defaults", [Limit(2, 5)])

    with pytest.raises(OpenShiftPythonException, match="Implicit and explicit defaults are mutually exclusive"):
        rate_limit.commit()
