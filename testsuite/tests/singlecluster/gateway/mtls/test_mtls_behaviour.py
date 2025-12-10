"""
Tests the enabling and disabling of mTLS configuration via the Kuadrant CR
"""

import pytest

pytestmark = [pytest.mark.disruptive]

component_cases = [
    pytest.param(["limitador"], id="limitador-only"),
    pytest.param(["authorino"], id="authorino-only"),
    pytest.param(["limitador", "authorino"], id="both-components"),
]


def assert_request_behavior(component, client, authorization, auth, rate_limit):
    """Sends requests based on the active components and checks expected response behavior"""
    if "limitador" in component:
        rate_limit.wait_for_ready()

        responses = client.get_many("/anything/limitador", 2)
        responses.assert_all(status_code=200)

        response = client.get("/anything/limitador")
        assert response.status_code == 429

    if "authorino" in component:
        authorization.wait_for_ready()

        response = client.get("/anything/authorino", auth=auth)
        assert response.status_code == 200

        response = client.get("/anything/authorino")
        assert response.status_code == 401


@pytest.mark.parametrize("component", component_cases, indirect=True)
def test_requests_succeed_when_mtls_disabled(
    kuadrant, client, component, rate_limit, authorization, auth, configure_mtls
):  # pylint: disable=unused-argument
    """Tests that requests succeed when mTLS is disabled"""
    configure_mtls(False)

    for comp in component:
        assert kuadrant.model.status.get(f"mtls{comp.capitalize()}") in (False, None)

    # Verify request behaviour based on active component/components
    assert_request_behavior(component, client, authorization, auth, rate_limit)


@pytest.mark.parametrize("component", component_cases, indirect=True)
def test_requests_succeed_when_mtls_enabled(
    kuadrant, client, component, rate_limit, authorization, auth, reset_mtls, wait_for_status, configure_mtls
):  # pylint: disable=unused-argument
    """Tests that requests succeed when mTLS is enabled"""
    configure_mtls(True)

    for comp in component:
        wait_for_status(expected=True, component=comp)
        assert kuadrant.model.status.get(f"mtls{comp.capitalize()}") is True

    for comp in {"limitador", "authorino"} - set(component):
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
    # Ensure mTLS was enabled before disabling it
    configure_mtls(True)

    for comp in component:
        wait_for_status(expected=True, component=comp)

    configure_mtls(False)

    for comp in component:
        wait_for_status(expected=False, component=comp)
        assert kuadrant.model.status.get(f"mtls{comp.capitalize()}") in (False, None)

    assert_request_behavior(component, client, authorization, auth, rate_limit)
