"""Conftest for all tests requiring custom deployment of Authorino"""
import pytest

from testsuite.openshift.objects.authorino import Authorino


@pytest.fixture(scope="session")
def authorino(openshift, blame, request):
    """Custom deployed Authorino instance"""
    authorino = Authorino.create_instance(openshift, blame("authorino"))
    request.addfinalizer(lambda: authorino.delete(ignore_not_found=True))
    authorino.commit()
    authorino.wait_for_ready()
    return authorino
