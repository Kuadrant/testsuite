"""Test mutual exclusivity of overrides block with explicit and implicit defaults"""

import pytest
from openshift_client import OpenShiftPythonException

from testsuite.kuadrant.policy.rate_limit import Limit

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def authorization_implicit(authorization, oidc_provider):
    """Create AuthPolicy with basic oidc rules inside and outside defaults block"""
    authorization.overrides.identity.add_oidc("inside-defaults", oidc_provider.well_known["issuer"])
    authorization.rules.identity.add_oidc("outside-defaults", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def rate_limit_implicit(rate_limit):
    """Add basic rate limiting rules inside and outside defaults block"""
    rate_limit.overrides.add_limit("inside-defaults", [Limit(2, 5)])
    rate_limit.limits.add_limit("outside-defaults", [Limit(2, 5)])
    return rate_limit


@pytest.fixture(scope="module")
def authorization_explicit(authorization, oidc_provider):
    """Create AuthPolicy with basic oidc rules inside and outside defaults block"""
    authorization.overrides.identity.add_oidc("inside-defaults", oidc_provider.well_known["issuer"])
    authorization.defaults.identity.add_oidc("outside-defaults", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def rate_limit_explicit(rate_limit):
    """Add basic rate limiting rules inside and outside defaults block"""
    rate_limit.overrides.add_limit("inside-defaults", [Limit(2, 5)])
    rate_limit.defaults.add_limit("outside-defaults", [Limit(2, 5)])
    return rate_limit


@pytest.fixture(scope="module")
def commit():
    """We need to try to commit objects during the actual test"""
    return None


@pytest.mark.parametrize(
    "component_fixture",
    [
        pytest.param("authorization_implicit", id="AuthPolicyImplicitDefault"),
        pytest.param("rate_limit_implicit", id="RateLimitPolicyImplicitDefault"),
    ],
)
def test_rules_exclusivity_implicit(request, component_fixture):
    """Test that server will reject object with implicit and explicit defaults defined simultaneously"""
    component = request.getfixturevalue(component_fixture)
    with pytest.raises(OpenShiftPythonException, match=r".*are mutually exclusive"):
        component.commit()


@pytest.mark.parametrize(
    "component_fixture",
    [
        pytest.param("authorization_explicit", id="AuthPolicyExplicitDefault"),
        pytest.param("rate_limit_explicit", id="RateLimitPolicyExplicitDefault"),
    ],
)
def test_rules_exclusivity_explicit(request, component_fixture):
    """Test that server will reject object with implicit and explicit defaults defined simultaneously"""
    component = request.getfixturevalue(component_fixture)
    with pytest.raises(OpenShiftPythonException, match=r".*verrides and explicit defaults are mutually exclusive"):
        component.commit()
