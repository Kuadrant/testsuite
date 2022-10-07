"""Root conftest for glbc tests"""
import pytest

from testsuite.openshift.httpbin import Httpbin


@pytest.fixture(scope="session")
def backend(request, kcp, blame, label):
    """Deploys Httpbin backend"""
    httpbin = Httpbin(kcp, blame("httpbin"), label)
    request.addfinalizer(httpbin.delete)
    httpbin.commit()
    return httpbin
