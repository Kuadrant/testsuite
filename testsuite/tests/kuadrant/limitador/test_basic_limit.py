"""
Tests that a single limit is enforced as expected over one iteration
"""
import pytest

from testsuite.openshift.objects.rate_limit import Limit
from testsuite.utils import fire_requests


@pytest.fixture(
    scope="module",
    params=[
        pytest.param(Limit(2, 20), id="2 requests every 20 sec"),
        pytest.param(Limit(5, 15), id="5 requests every 15 sec"),
        pytest.param(Limit(3, 10), id="3 request every 10 sec"),
    ],
)
def limit(request):
    """Combination of max requests and time period"""
    return request.param


# pylint: disable=unused-argument
@pytest.fixture(scope="module")
def rate_limit_name(blame, limit):
    """Generate name for each combination of limit_time"""
    return blame("limit")


@pytest.fixture(scope="module")
def rate_limit(rate_limit, limit):
    """Add limit to the policy"""
    rate_limit.add_limit("basic", [limit])
    return rate_limit


def test_limit(client, limit):
    """Tests that simple limit is applied successfully"""
    fire_requests(client, limit, grace_requests=1)
