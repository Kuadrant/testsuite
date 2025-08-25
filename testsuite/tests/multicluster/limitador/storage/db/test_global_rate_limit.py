"""Test for multicluster global rate limiting feature with a shared Redis backend."""

import pytest
from testsuite.kuadrant.limitador import Redis
from testsuite.kuadrant.policy.rate_limit import Limit


pytestmark = [pytest.mark.multicluster, pytest.mark.limitador, pytest.mark.disruptive]


@pytest.fixture(scope="module")
def storage1(storage_secret1):
    """Returns Redis storage configuration for the first cluster."""
    return Redis(storage_secret1.name())


@pytest.fixture(scope="module")
def storage2(storage_secret2):
    """Returns Redis storage configuration for the second cluster."""
    return Redis(storage_secret2.name())


@pytest.fixture(scope="module")
def limit():
    """Returns the specific Limit object for this test module."""
    return Limit(5, "300s")


def test_global_limit_is_shared(
    client, configured_limitador1, configured_limitador2, limit, gateway, gateway2
):  # pylint: disable=unused-argument
    """
    Tests that the counter is shared between two clusters using a central Redis.
    The shared client will automatically be load-balanced between the two clusters.

    Note: configured_limitador1, configured_limitador2, gateway, gateway2 are needed
    for test setup even though not directly used in the test body.
    """
    # Make requests that should be distributed across both clusters
    # Due to DNS load balancing, requests will hit both clusters
    responses = client.get_many("/get", limit.limit)
    responses.assert_all(status_code=200)

    # The next request should be rate limited since we've hit the global limit
    assert client.get("/get").status_code == 429
