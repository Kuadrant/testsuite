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
    return Limit(5, "30s")


def test_global_limit_is_shared(
    client1,
    client2,
    limit,
):  # pylint: disable=unused-argument
    """
    Tests that the counter is shared between two clusters using a central Redis.
    It sends requests to each cluster to exhaust the shared rate limit, and then
    verifies that subsequent requests are rejected.
    """
    requests_to_cluster1 = limit.limit // 2
    requests_to_cluster2 = limit.limit - requests_to_cluster1

    if requests_to_cluster1 > 0:
        responses1 = client1.get_many("/get", requests_to_cluster1)
        responses1.assert_all(status_code=200)

    if requests_to_cluster2 > 0:
        responses2 = client2.get_many("/get", requests_to_cluster2)
        responses2.assert_all(status_code=200)

    assert client1.get("/get").status_code == 429
    assert client2.get("/get").status_code == 429
