"""Test mutual exclusivity of overrides block with explicit and implicit defaults"""

import pytest
from openshift_client import OpenShiftPythonException

from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.fixture(scope="module")
def commit():
    """We need to try to commit objects during the actual test"""
    return None


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/775")
def test_rules_exclusivity_implicit_authorization(cluster, route, oidc_provider, module_label, blame):
    """Test that server will reject an AuthPolicy with overrides and implicit defaults defined simultaneously"""
    authorization = AuthPolicy.create_instance(cluster, blame("authz"), route, labels={"testRun": module_label})
    authorization.overrides.identity.add_oidc("overrides", oidc_provider.well_known["issuer"])
    authorization.identity.add_oidc("implicit-defaults", oidc_provider.well_known["issuer"])

    with pytest.raises(
        OpenShiftPythonException, match="Implicit defaults and explicit overrides are mutually exclusive"
    ):
        authorization.commit()


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/775")
def test_rules_exclusivity_explicit_authorization(cluster, route, oidc_provider, module_label, blame):
    """Test that server will reject an AuthPolicy with overrides and implicit defaults defined simultaneously"""
    authorization = AuthPolicy.create_instance(cluster, blame("authz"), route, labels={"testRun": module_label})
    authorization.overrides.identity.add_oidc("overrides", oidc_provider.well_known["issuer"])
    authorization.defaults.identity.add_oidc("explicit-defaults", oidc_provider.well_known["issuer"])

    with pytest.raises(
        OpenShiftPythonException, match="Explicit overrides and explicit defaults are mutually exclusive"
    ):
        authorization.commit()


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/775")
def test_rules_exclusivity_implicit_rate_limit(cluster, route, module_label, blame):
    """Test that server will reject a RateLimitPolicy with overrides and implicit defaults defined simultaneously"""
    rate_limit = RateLimitPolicy.create_instance(cluster, blame("limit"), route, labels={"testRun": module_label})
    rate_limit.overrides.add_limit("overrides", [Limit(2, "5s")])
    rate_limit.add_limit("implicit-defaults", [Limit(2, "5s")])

    with pytest.raises(OpenShiftPythonException, match="Overrides and implicit defaults are mutually exclusive"):
        rate_limit.commit()


@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/775")
def test_rules_exclusivity_explicit_rate_limit(cluster, route, module_label, blame):
    """Test that server will reject a RateLimitPolicy with overrides and explicit defaults defined simultaneously"""
    rate_limit = RateLimitPolicy.create_instance(cluster, blame("limit"), route, labels={"testRun": module_label})
    rate_limit.overrides.add_limit("overrides", [Limit(2, "5s")])
    rate_limit.defaults.add_limit("explicit-defaults", [Limit(2, "5s")])

    with pytest.raises(OpenShiftPythonException, match="Overrides and explicit defaults are mutually exclusive"):
        rate_limit.commit()
