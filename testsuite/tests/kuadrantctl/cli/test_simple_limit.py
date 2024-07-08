"""
Tests that you can generate simple RateLimitPolicy, focused on the cmdline options more than on extension
functionality
"""

import pytest

from testsuite.oas import as_tmp_file
from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy
from testsuite.utils import asdict


@pytest.fixture(scope="module")
def oas(oas, blame, gateway, hostname, backend):
    """Add X-Kuadrant specific fields"""
    oas.add_top_level_route(gateway, hostname, blame("route"))
    oas.add_backend_to_paths(backend)

    oas["paths"]["/anything"]["get"]["x-kuadrant"] = {"rate_limit": {"rates": [asdict(Limit(3, 20))]}}
    return oas


@pytest.mark.parametrize("encoder", [pytest.param("as_json", id="JSON"), pytest.param("as_yaml", id="YAML")])
@pytest.mark.parametrize("stdin", [pytest.param(True, id="STDIN"), pytest.param(False, id="File")])
def test_generate_limit(request, kuadrantctl, oas, encoder, cluster, client, stdin):
    """Tests that RateLimitPolicy can be generated and that it is enforced as expected"""
    encoded = getattr(oas, encoder)()

    if stdin:
        result = kuadrantctl.run("generate", "kuadrant", "ratelimitpolicy", "--oas", "-", input=encoded)
    else:
        with as_tmp_file(encoded) as file_name:
            result = kuadrantctl.run("generate", "kuadrant", "ratelimitpolicy", "--oas", file_name)

    policy = cluster.apply_from_string(result.stdout, RateLimitPolicy)
    request.addfinalizer(policy.delete)
    policy.wait_for_ready()

    responses = client.get_many("/anything", 3)
    responses.assert_all(status_code=200)
    assert client.get("/anything").status_code == 429

    # Check that it did not affect other endpoints
    responses = client.get_many("/get", 5)
    responses.assert_all(status_code=200)
