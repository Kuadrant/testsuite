"""
    Test that will set up authorino and prepares objects for performance testing.
    Fill necessary data to benchmark template.
    Run the test and assert results.
"""
from urllib.parse import urlparse
from importlib import resources

import backoff
import pytest

from testsuite.perf_utils import HyperfoilUtils, prepare_url

# Maximal runtime of test (need to cover all performance stages)
MAX_RUN_TIME = 10 * 60
# Number of Hyperfoil agents to be spawned
AGENTS = 2

pytestmark = [pytest.mark.performance]


@pytest.fixture(scope='module')
def number_of_agents():
    """Number of spawned HyperFoil agents"""
    return AGENTS


@pytest.fixture(scope='module')
def template():
    """Path to template"""
    return resources.files("testsuite.tests.kuadrant.authorino.performance.templates")\
        .joinpath('template_perf_basic_query_rhsso.hf.yaml')


@pytest.fixture(scope='module')
def hyperfoil_utils(hyperfoil_client, template, request):
    """Init of hyperfoil utils"""
    utils = HyperfoilUtils(hyperfoil_client, template)
    request.addfinalizer(utils.delete)
    utils.commit()
    return utils


@pytest.fixture(scope='module')
def setup_benchmark_rhsso(hyperfoil_utils, client, rhsso, number_of_agents):
    """Setup of benchmark. It will add necessary host connections, csv data and files."""
    # currently number of shared connections is set as a placeholder and later should be determined by test results
    url_pool = [{'url': rhsso.server_url, 'connections': 100}, {'url': str(client.base_url), 'connections': 20}]
    for url in url_pool:
        complete_url = prepare_url(urlparse(url['url']))
        hyperfoil_utils.add_host(complete_url._replace(path="").geturl(), shared_connections=url['connections'])

    hyperfoil_utils.add_rhsso_auth_token(rhsso, prepare_url(urlparse(str(client.base_url))).netloc, 'rhsso_auth.csv')
    hyperfoil_utils.add_file(HyperfoilUtils.message_1kb)
    hyperfoil_utils.add_shared_template(number_of_agents)
    return hyperfoil_utils


@backoff.on_predicate(backoff.constant, lambda x: not x.is_finished(), interval=5, max_time=MAX_RUN_TIME)
def wait_run(run):
    """Waits for the run to end"""
    return run.reload()


def test_basic_perf_rhsso(client, rhsso_auth, setup_benchmark_rhsso):
    """
       Test checks that authorino is set up correctly.
       Runs the created benchmark.
       Asserts it was successful.
    """
    get_response = client.get("/get", auth=rhsso_auth)
    post_response = client.post("/post", auth=rhsso_auth)
    assert get_response.status_code == 200
    assert post_response.status_code == 200

    benchmark = setup_benchmark_rhsso.create_benchmark()
    run = benchmark.start()

    run = wait_run(run)

    stats = run.all_stats()

    assert stats
    assert stats.get('info', {}).get('errors') == []
    assert stats.get('failures') == []
    assert stats.get('stats', []) != []
