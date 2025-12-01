"""Limitador storage tests with Disk storage option"""

import pytest

from testsuite.kuadrant.limitador import Disk
from ..conftest import LIMIT

pytestmark = [pytest.mark.limitador, pytest.mark.disruptive]


@pytest.fixture(scope="module")
def storage():
    """Storage dataclass to be used for this module: Disk"""
    return Disk()


def test_basic(client):
    """Tests that limits work normally in storage environment"""
    responses = client.get_many("/get", LIMIT.limit)
    responses.assert_all(status_code=200)
    assert client.get("/get").status_code == 429


def test_durability(client, limitador, rate_limit):
    """
    Basic test checking that after Limitador pod restart, counters are preserved.
    'hard' rollout is required due to pod getting stuck in graceful rollout
        see https://github.com/Kuadrant/limitador-operator/issues/196
    """
    responses = client.get_many("/get", LIMIT.limit)
    responses.assert_all(status_code=200)
    limitador.deployment.rollout(hard=True)
    limitador.wait_for_ready()
    rate_limit.wait_for_ready()
    assert client.get("/get").status_code == 429
