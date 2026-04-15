"""Test: AuthPolicy reads a K8s Secret via metadata.http and injects it as a request header.

Based on https://github.com/Kuadrant/architecture/issues/148
Pattern: metadata.http fetches credential from K8s API, response.success.headers injects it upstream.
Uses MockServer as the backend to validate injected credentials:
  - Correct Authorization header -> 200
  - Wrong or missing header -> 401
"""

import pytest

from testsuite.gateway import CustomReference, URLRewriteFilter
from testsuite.gateway.gateway_api.route import HTTPRoute

from ..conftest import EGRESS_HOSTNAME

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.egress_gateway]


@pytest.fixture(scope="module")
def route(request, gateway, cluster, blame, hostname, module_label, service_entry, destination_rule):
    """HTTPRoute routing egress traffic through the gateway to the backend"""
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


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization):
    """Commit the AuthPolicy and wait for it to be enforced"""
    request.addfinalizer(authorization.delete)
    authorization.commit()
    authorization.wait_for_ready()


def test_egress_credential_injection(client, mockserver_expectation):
    """Test that the correct credential is accepted (200) and that no injected credential results in rejection (401)"""
    response = client.get(mockserver_expectation)
    assert response.status_code == 200

    response = client.get(mockserver_expectation, headers={"dont-inject": "true"})
    assert response.status_code == 401
