"""Test that checks if requests that are blocked by Authorino do not reach the backend"""

import pytest

from testsuite.kuadrant.policy.authorization import DenyResponse, Value
from testsuite.utils import rego_allow_header


@pytest.fixture(scope="module")
def require_observability_disabled(kuadrant):
    """
    Skip test if tracing is enabled in the Kuadrant CR.
    This test does not verify properly with tracing enabled
    """
    tracing_spec = kuadrant.model.spec.get("observability", {}).get("tracing")
    if tracing_spec is not None and tracing_spec.get("defaultEndpoint") is not None:
        pytest.skip("This test does not verify properly with tracing enabled")


@pytest.fixture(scope="module")
def authorization(authorization):
    """
    Adds OPA policy that accepts all requests that contain `header`
    Adds unauthorized message as it adds processing delay, increasing the chance for the bug to appear.
    """
    authorization.identity.clear_all()
    authorization.authorization.add_opa_policy("opa", rego_allow_header("key", "value"))
    authorization.responses.set_unauthorized(DenyResponse(body=Value("Custom response")))
    return authorization


@pytest.mark.issue("https://github.com/Kuadrant/wasm-shim/pull/321")
def test_backend_not_reached(client, require_observability_disabled):  # pylint: disable=unused-argument
    """
    Get current value of the counter. This counter increments by every request.
    Do unauthorized requests which should not increment the counter.
    Lastly check the counter if it contains expected value.
    """
    before_counter = client.get("/counter", headers={"key": "value"}).json()["counter"]
    client.get_many("/counter", 10)
    after_counter = client.get("/counter", headers={"key": "value"}).json()["counter"]
    assert after_counter == before_counter + 1
