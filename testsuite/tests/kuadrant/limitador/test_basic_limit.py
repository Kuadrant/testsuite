"""
Tests that a single limit is enforced as expected over one iteration
"""
import pytest

from testsuite.utils import fire_requests


@pytest.fixture(
    scope="module",
    params=[
        pytest.param((2, 20), id="2 requests every 20 sec"),
        pytest.param((5, 15), id="5 requests every 15 sec"),
        pytest.param((3, 10), id="3 request every 10 sec"),
    ],
)
def limit_time(request):
    """Combination of max requests and time period"""
    return request.param


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def rate_limit_name(blame, limit_time):
    """Generate name for each combination of limit_time"""
    return blame("limit")


@pytest.fixture(scope="module")
def rate_limit(rate_limit, limit_time):
    """Add limit to the policy"""
    limit, time = limit_time
    rate_limit.add_limit(limit, time)
    return rate_limit


def test_limit(client, limit_time):
    """Tests that simple limit is applied successfully"""
    limit, time = limit_time

    fire_requests(client, limit, time, grace_requests=1)
