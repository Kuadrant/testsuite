"""
Conftest for performance tests
"""

import os
import warnings
from datetime import datetime
from pathlib import Path

import pytest
from dynaconf import ValidationError
from weakget import weakget

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.hyperfoil import Hyperfoil, StartedRun


@pytest.fixture(scope="session")
def hyperfoil(testconfig):
    """Hyperfoil client"""
    try:
        return Hyperfoil(testconfig["hyperfoil"]["url"])
    except (KeyError, ValidationError) as exc:
        return pytest.skip(f"Hyperfoil configuration item is missing: {exc}")


@pytest.fixture(scope="module")
def agents():
    """Agent configuration for benchmark"""
    return {"agents": [{"agent-1": {"host": "localhost", "port": 22}}]}


@pytest.fixture(scope="module")
def http():
    """HTTP configured of the benchmark, contains hosts"""
    return {}


@pytest.fixture(scope="module")
def files():
    """All files required by the benchmark"""
    return {}


@pytest.fixture(scope="module")
def name():
    """Name of the benchmark"""
    return None


@pytest.fixture(scope="module")
def benchmark(hyperfoil, name, template, agents, http, files):
    """Create new benchmark"""
    return hyperfoil.create_benchmark(name, agents, http, template, files)


@pytest.fixture(scope="module")
def rhsso_auth(rhsso):
    """Returns RHSSO authentication object for HTTPX"""
    return HttpxOidcClientAuth(rhsso.get_token)


@pytest.fixture(scope="function")
def generate_report(request, testconfig):
    """Generates HTML report for the performance test"""
    generate = weakget(testconfig)["hyperfoil"]["generate_reports"] % True
    if not generate:
        return lambda _: None

    directory = weakget(testconfig)["hyperfoil"]["report_dir"] % None
    if not directory:
        warnings.warn("Unable to save report, report_dir is missing in configuration")
        return lambda _: None

    directory = Path(directory)
    if not os.path.exists(directory):
        os.makedirs(directory)

    def _gen(run: StartedRun):
        name = f"{request.node.name}-{datetime.now().strftime('%d%m%Y-%H%M')}.html"
        run.report(name, directory)
        warnings.warn(f"Report for test {request.node.name} is saved at {directory}/{name}")

    return _gen
