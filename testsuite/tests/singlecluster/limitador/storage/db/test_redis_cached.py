"""Limitador storage tests with RedisCached storage option"""

import pytest

from testsuite.kuadrant.limitador import RedisCached
from ..conftest import LIMIT

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador, pytest.mark.disruptive]


@pytest.fixture(scope="module")
def storage(storage_secret):
    """
    Storage dataclass to be used for this module: RedisCached
    Relevant options were lowered to minimum to minimize effect of caching on the test.
    But the test works even without setting these.
    """
    return RedisCached(storage_secret.name(), flush_period=1, batch_size=1, max_cached=1)


def test_basic(client):
    """Tests that limits work normally in storage environment"""
    responses = client.get_many("/get", LIMIT.limit)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429


@pytest.mark.issue("https://github.com/Kuadrant/limitador-operator/issues/197")
@pytest.mark.xfail(reason="https://github.com/Kuadrant/limitador-operator/issues/197")
def test_durability(client, limitador, rate_limit):
    """Basic test checking that after Limitador pod restart, counters are preserved."""
    responses = client.get_many("/get", LIMIT.limit)
    responses.assert_all(status_code=200)
    limitador.deployment.rollout()
    limitador.wait_for_ready()
    rate_limit.wait_for_ready()
    assert client.get("/get").status_code == 429
