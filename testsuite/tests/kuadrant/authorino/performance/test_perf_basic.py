"""
    Test that will set up authorino and prepares objects for performance testing.
    Fill necessary data to benchmark template.
    Run the test and assert results.
"""

from importlib import resources

import pytest
import yaml

from testsuite.utils import add_port, create_csv_file, MESSAGE_1KB

# Maximal runtime of test (need to cover all performance stages)
MAX_RUN_TIME = 10 * 60

pytestmark = [pytest.mark.performance]


@pytest.fixture(scope="module")
def name():
    """Name of the benchmark"""
    return "test_perf_basic"


@pytest.fixture(scope="module")
def template():
    """Template path"""
    path = resources.files("testsuite.tests.kuadrant.authorino.performance.templates").joinpath(
        "template_perf_basic_query_rhsso.hf.yaml"
    )
    with path.open("r", encoding="UTF-8") as stream:
        return yaml.safe_load(stream)


@pytest.fixture(scope="module")
def http(keycloak, client):
    """Configures host for the gateway and Keycloak"""
    return {
        "http": [
            {"host": add_port(keycloak.server_url), "sharedConnections": 100},
            {"host": add_port(str(client.base_url)), "sharedConnections": 20},
        ]
    }


@pytest.fixture(scope="module")
def files(keycloak, client):
    """Adds Message and Keycloak CSV to the files"""
    token_url_obj = add_port(keycloak.well_known["token_endpoint"], return_netloc=False)
    client_url = add_port(str(client.base_url))
    with MESSAGE_1KB.open("r", encoding="UTF-8") as file:
        yield {
            "message_1kb.txt": file,
            "keycloak_auth.csv": create_csv_file(
                [[client_url, token_url_obj.netloc, token_url_obj.path, keycloak.token_params()]]
            ),
        }


def test_basic_perf_rhsso(generate_report, client, benchmark, keycloak_auth, blame):
    """
    Test checks that authorino is set up correctly.
    Runs the created benchmark.
    Asserts it was successful.
    """
    assert client.get("/get", auth=keycloak_auth).status_code == 200
    run = benchmark.start(blame("run"))

    obj = run.wait(MAX_RUN_TIME)
    assert obj["completed"], "Ran out of time"

    generate_report(run)
    stats = run.stats()

    assert stats
    info = stats.get("info", {})
    assert len(info.get("errors")) == 0, f"Errors occured: {info.get('errors')}"
    assert stats.get("failures") == []
    assert stats.get("stats", []) != []
