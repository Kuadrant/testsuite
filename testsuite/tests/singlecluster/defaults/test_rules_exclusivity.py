"""Test mutual exclusivity of defaults block and implicit defaults"""

import pytest
from openshift_client import OpenShiftPythonException

from testsuite.kuadrant.policy.rate_limit import Limit

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """Create AuthPolicy with basic oidc rules inside and outside defaults block"""
    authorization.defaults.identity.add_oidc("inside-defaults", oidc_provider.well_known["issuer"])
    authorization.rules.identity.add_oidc("outside-defaults", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add basic rate limiting rules inside and outside defaults block"""
    rate_limit.defaults.add_limit("inside-defaults", [Limit(2, 5)])
    rate_limit.limits.add_limit("outside-defaults", [Limit(2, 5)])
    return rate_limit


@pytest.fixture(scope="module")
def commit():
    """We need to try to commit objects during the actual test"""
    return None


@pytest.mark.parametrize(
    "component_fixture",
    [
        pytest.param("authorization", id="AuthPolicy"),
        pytest.param("rate_limit", id="RateLimitPolicy"),
    ],
)
def test_rules_exclusivity(request, component_fixture):
    """Test that server will reject object with implicit and explicit defaults defined simultaneously"""
    component = request.getfixturevalue(component_fixture)
    with pytest.raises(OpenShiftPythonException, match="Implicit and explicit defaults are mutually exclusive"):
        component.commit()
