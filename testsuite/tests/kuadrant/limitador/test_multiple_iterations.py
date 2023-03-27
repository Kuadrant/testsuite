"""
Tests that a single limit is enforced as expected over multiple iterations
"""
import pytest

from testsuite.utils import fire_requests


@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limit to the policy"""
    rate_limit.add_limit(5, 10)
    return rate_limit


def test_multiple_iterations(client):
    """Tests that simple limit is applied successfully and works for multiple iterations"""
    fire_requests(client, 5, 10, iterations=10)
