"""Test gateway level default merging with and being partially overriden by another policy."""

import pytest

from testsuite.kuadrant.policy import has_condition
from testsuite.tests.singlecluster.defaults.merge.rate_limit.conftest import MERGE_LIMIT2, LIMIT

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.limitador]


@pytest.mark.parametrize("rate_limit", [{"section": None}], indirect=True)
def test_gateway_default_replace(client, global_rate_limit):
    """Test Gateway default policy being partially overridden when a policy with the same name is attached on a route"""
    assert global_rate_limit.wait_until(
        has_condition("Enforced", "True", "Enforced", "RateLimitPolicy has been partially enforced")
    )

    get = client.get_many("/get", LIMIT.limit)
    get.assert_all(status_code=200)
    assert client.get("/get").status_code == 429

    anything = client.get_many("/anything", MERGE_LIMIT2.limit)
    anything.assert_all(status_code=200)
    assert client.get("/anything").status_code == 429
