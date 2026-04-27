"""Tests for AuthPolicy and RateLimitPolicy with egress gateway.

Based on https://github.com/Kuadrant/architecture/issues/147#issuecomment-4053003829
Sets up an egress gateway with Istio's ServiceEntry, DestinationRule,
and HTTPRoute with URLRewrite filter to route egress traffic to an externally deployed service.
Validates that AuthPolicy and RateLimitPolicy are enforced on egress traffic.
"""

from time import sleep

import pytest

from testsuite.gateway import CustomReference, URLRewriteFilter
from testsuite.gateway.gateway_api.route import HTTPRoute
from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy.rate_limit import Limit
from .conftest import EGRESS_HOSTNAME

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.egress_gateway]

LIMIT = Limit(3, "5s")


@pytest.fixture(scope="module")
def route(request, gateway, cluster, blame, hostname, module_label, service_entry, destination_rule):
    """HTTPRoute routing egress traffic through the gateway to the backend via Hostname backendRef"""
    # pylint: disable=unused-argument
    route = HTTPRoute.create_instance(cluster, blame("route"), gateway, {"app": module_label})
    route.add_hostname(EGRESS_HOSTNAME)
    route.add_rule(
        CustomReference(group="networking.istio.io", kind="Hostname", name=hostname.hostname, port=443),
        filters=[URLRewriteFilter(hostname=hostname.hostname)],
    )
    request.addfinalizer(route.delete)
    route.commit()
    route.wait_for_ready()
    return route


@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """Add OIDC identity to AuthPolicy for egress"""
    authorization.identity.add_oidc("oidc", oidc_provider.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add rate limit to RateLimitPolicy for egress"""
    rate_limit.add_limit("3_5s", [LIMIT])
    return rate_limit


@pytest.fixture(scope="module")
def auth(oidc_provider):
    """Returns OIDC authentication object for HTTPX"""
    return HttpxOidcClientAuth(oidc_provider.get_token, "authorization")


def test_egress_authorization(client, auth):
    """Test that AuthPolicy is enforced on egress gateway traffic"""
    assert client.get("/get").status_code == 401

    response = client.get("/get", auth=auth)
    assert response.status_code == 200


@pytest.mark.flaky(reruns=3, reruns_delay=10)
def test_egress_ratelimit(client, auth):
    """Test that RateLimitPolicy is enforced on egress gateway traffic"""
    sleep(5 + 1)  # make sure request limit quota is reset before starting the test

    responses = client.get_many("/get", LIMIT.limit, auth=auth)
    responses.assert_all(status_code=200)

    assert client.get("/get", auth=auth).status_code == 429
