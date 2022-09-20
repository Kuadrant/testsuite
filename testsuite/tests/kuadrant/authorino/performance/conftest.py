"""
Conftest for performance tests
"""
import pytest
import os

from pathlib import Path
from hyperfoil import HyperfoilClient

from testsuite.perf_utils import HyperfoilUtils
from testsuite.httpx.auth import HttpxOidcClientAuth


@pytest.fixture(scope='session')
def hyperfoil_client(testconfig):
    """Hyperfoil client"""
    client = HyperfoilClient(testconfig['hyperfoil']['url'])
    return client


@pytest.fixture(scope='module')
def hyperfoil_utils(hyperfoil_client, template, request):
    """Init of hyperfoil utils"""
    utils = HyperfoilUtils(hyperfoil_client, template)
    request.addfinalizer(utils.finalizer)
    return utils


@pytest.fixture(scope='module')
def shared_template(testconfig):
    """Shared template for hyperfoil test"""
    shared_template = testconfig.get('hyperfoil', {}).get('shared_template', {})
    return shared_template.to_dict()


@pytest.fixture(scope='session')
def root_path():
    """Root path for performance tests"""
    return Path(os.path.realpath(__file__)).parent


@pytest.fixture(scope="module")
def rhsso_authorization(authorization, rhsso):
    """Add RHSSO identity to AuthConfig"""
    authorization.add_oidc_identity("rhsso", rhsso.well_known["issuer"])
    return authorization


@pytest.fixture(scope="module")
def rhsso_auth(rhsso):
    """Returns RHSSO authentication object for HTTPX"""
    return HttpxOidcClientAuth(rhsso.get_token)
