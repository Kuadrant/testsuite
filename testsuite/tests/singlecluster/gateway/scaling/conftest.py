"""Conftest for the auto scale gateway test"""

import pytest
from testsuite.custom_metrics_apiserver.client import CustomMetricsApiServerClient
from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, Limit

LIMIT = Limit(3, "5s")


@pytest.fixture(scope="session")
def custom_metrics_apiserver(testconfig):
    """Deploys Httpbin backend"""
    testconfig.validators.validate(only="custom_metrics_apiserver")
    return CustomMetricsApiServerClient(testconfig["custom_metrics_apiserver"]["url"])


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """Create an AuthPolicy with authentication for a simple user with same target as one default"""
    authorization.identity.add_oidc(
        "default", oidc_provider.well_known["issuer"], when=[CelPredicate("request.path == '/anything/auth'")]
    )
    # Anonymous auth for /anything/limitador
    authorization.identity.add_anonymous(
        "allow-limitador-anonymous", when=[CelPredicate("request.path == '/anything/limit'")]
    )
    return authorization


@pytest.fixture(scope="module")
def rate_limit(blame, gateway, module_label, cluster):
    """Add limit to the policy"""
    policy = RateLimitPolicy.create_instance(cluster, blame("rlp"), gateway, labels={"app": module_label})
    policy.add_limit("basic", [LIMIT], when=[CelPredicate("request.path == '/anything/limit'")])
    return policy


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, rate_limit, dns_policy, tls_policy):
    """Commits all important stuff before tests"""
    for component in [dns_policy, tls_policy, authorization, rate_limit]:
        request.addfinalizer(component.delete)
        component.commit()
        component.wait_for_ready()
