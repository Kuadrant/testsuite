"""Tests that wasm-shim policy enforcement works regardless of hostname case in the request"""

from time import sleep

import pytest

from testsuite.httpx import KuadrantClient
from testsuite.httpx.auth import HeaderApiKeyAuth
from testsuite.kuadrant.policy.rate_limit import Limit
from testsuite.utils.constants import RLP_ITERATION_WINDOW_RESET_WAIT

pytestmark = [pytest.mark.limitador, pytest.mark.authorino, pytest.mark.kuadrant_only]


@pytest.fixture(scope="module")
def api_key(create_api_key, module_label):
    """Creates API key Secret"""
    return create_api_key("api-key", module_label, "api_key_value")


@pytest.fixture(scope="module")
def auth(api_key):
    """Valid API Key Auth"""
    return HeaderApiKeyAuth(api_key)


@pytest.fixture(scope="module")
def authorization(authorization, api_key):
    """Add API key identity to the AuthPolicy"""
    authorization.identity.add_api_key("api-key", selector=api_key.selector)
    return authorization


@pytest.fixture(scope="module")
def client(route, gateway):  # pylint: disable=unused-argument
    """Client that connects directly to the gateway IP, bypassing the OpenShift router.
    On OCP, the router (HAProxy) lowercases the Host header before it reaches the Istio gateway,
    which prevents the wasm-shim from ever seeing the case mismatch we need to test."""
    client = KuadrantClient(base_url=f"http://{gateway.external_ip()}")
    yield client
    client.close()


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add a simple rate limit"""
    rate_limit.add_limit("basic", [Limit(3, "10s")])
    return rate_limit


@pytest.mark.issue("https://github.com/Kuadrant/wasm-shim/pull/405")
@pytest.mark.parametrize(
    "case_transform",
    [
        pytest.param(str.lower, id="lowercase"),
        pytest.param(str.upper, id="uppercase"),
        pytest.param(str.title, id="mixed-case"),
    ],
)
@pytest.mark.flaky(reruns=3, reruns_delay=15)
def test_rate_limit_hostname_case_insensitive(client, hostname, auth, case_transform):
    """Tests that wasm-shim enforces policies when the request hostname has different case"""
    mixed_case_host = case_transform(hostname.hostname)
    sleep(RLP_ITERATION_WINDOW_RESET_WAIT)

    responses = client.get_many("/get", 3, auth=auth, headers={"Host": mixed_case_host})
    responses.assert_all(status_code=200)
    assert client.get("/get", auth=auth, headers={"Host": mixed_case_host}).status_code == 429
