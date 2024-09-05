"""Test that overrides block can not be defined in AuthPolicy and RateLimitPolicy attached to a HTTPRoute"""

import pytest
from openshift_client import OpenShiftPythonException

from testsuite.kuadrant.policy.rate_limit import Limit

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """Create AuthPolicy with basic oidc rules in the overrides block"""
    authorization.overrides.identity.add_oidc("override", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add basic rate limiting rules in the overrides block"""
    rate_limit.overrides.add_limit("override", [Limit(2, 5)])
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
@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/775")
def test_route_override(request, component_fixture):
    """Test that server will reject policy attached to a HTTPRoute containing an overrides block"""
    component = request.getfixturevalue(component_fixture)
    with pytest.raises(OpenShiftPythonException, match="Overrides are.*"):
        component.commit()
