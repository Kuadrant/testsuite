"""
Tests the enabling and disabling of mTLS configuration via the Kuadrant CR
"""

import pytest

from testsuite.tests.singlecluster.gateway.mtls.conftest import get_components_to_check

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.disruptive]

component_cases = ["limitador", "authorino", "both"]


@pytest.fixture(scope="module")
def rate_limit(component, request):
    """Enable RateLimitPolicy when component is 'limitador' or 'both'"""
    if component in ("limitador", "both"):
        return request.getfixturevalue("rate_limit")
    return None


def assert_request_behavior(component, client, authorization, auth, rate_limit):
    """Sends requests based on the component and checks expected response behavior"""
    if component == "limitador":
        rate_limit.wait_for_ready()

        responses = client.get_many("/get", 2)
        responses.assert_all(status_code=200)
        assert client.get("/get").status_code == 429

    elif component == "authorino":
        authorization.wait_for_ready()
        response = client.get("/get", auth=auth)

        assert response.status_code == 200

        response = client.get("/get")
        assert response.status_code == 401

    elif component == "both":
        authorization.wait_for_ready()
        rate_limit.wait_for_ready()

        response = client.get("/get", auth=auth)
        assert response.status_code == 200

        response = client.get("/get")
        assert response.status_code == 401

        response = client.get("/get", auth=auth)
        assert response.status_code == 429


@pytest.mark.parametrize("component", component_cases, indirect=True)
def test_requests_succeed_when_mtls_disabled(
    kuadrant, client, component, rate_limit, authorization, auth, configure_mtls
):  # pylint: disable=unused-argument
    """Tests that requests succeed when mTLS is disabled"""
    configure_mtls(False)

    assert kuadrant.model.spec.mtls.enable is False

    components_to_check = get_components_to_check(component)
    for comp in components_to_check:
        assert kuadrant.model.status.get(f"mtls{comp.capitalize()}") in (False, None)

    # Verify request behaviour based on active component/components
    assert_request_behavior(component, client, authorization, auth, rate_limit)


@pytest.mark.parametrize("component", component_cases, indirect=True)
def test_requests_succeed_when_mtls_enabled(
    kuadrant, client, component, rate_limit, authorization, auth, reset_mtls, wait_for_status, configure_mtls
):  # pylint: disable=unused-argument
    """Tests that requests succeed when mTLS is enabled"""
    configure_mtls(True)

    all_components = ["limitador", "authorino"]
    enabled_components = [component] if component != "both" else all_components
    disabled_components = [c for c in all_components if c not in enabled_components]

    for comp in enabled_components:
        wait_for_status(kuadrant, expected=True, component=comp)

    assert kuadrant.model.spec.mtls.enable is True

    for comp in enabled_components:
        assert kuadrant.model.status.get(f"mtls{comp.capitalize()}") is True

    for comp in disabled_components:
        assert kuadrant.model.status.get(f"mtls{comp.capitalize()}") in (False, None)

    # Backoff on status_code 500 / 404 as wait for ready is not enough
    client.add_retry_code(500)
    client.add_retry_code(404)

    assert_request_behavior(component, client, authorization, auth, rate_limit)


@pytest.mark.parametrize("component", component_cases, indirect=True)
def test_requests_still_succeed_after_mtls_disabled_again(
    kuadrant, client, component, rate_limit, authorization, auth, wait_for_status, configure_mtls
):  # pylint: disable=unused-argument
    """Tests that requests succeed after disabling mTLS again"""
    configure_mtls(False)

    components_to_check = get_components_to_check(component)
    for comp in components_to_check:
        wait_for_status(kuadrant, expected=False, component=comp)

    assert kuadrant.model.spec.mtls.enable is False

    for comp in components_to_check:
        assert kuadrant.model.status.get(f"mtls{comp.capitalize()}") in (False, None)

    assert_request_behavior(component, client, authorization, auth, rate_limit)
