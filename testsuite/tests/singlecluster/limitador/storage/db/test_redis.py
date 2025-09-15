"""Limitador storage tests with Redis storage option"""

import pytest

from testsuite.kuadrant.limitador import Redis
from ..conftest import LIMIT

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador, pytest.mark.disruptive]


@pytest.fixture(scope="module")
def storage(storage_secret):
    """Storage dataclass to be used for this module: Redis"""
    return Redis(storage_secret.name())


def test_basic(client):
    """Tests that limits work normally in storage environment"""
    responses = client.get_many("/get", LIMIT.limit)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429


def test_durability(client, limitador, rate_limit):
    """Basic test checking that after Limitador pod restart, counters are preserved."""
    responses = client.get_many("/get", LIMIT.limit)
    responses.assert_all(status_code=200)
    limitador.deployment.rollout()
    limitador.wait_for_ready()
    rate_limit.wait_for_ready()
    assert client.get("/get").status_code == 429
