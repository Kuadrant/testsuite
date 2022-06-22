"""Conftest for all tests requiring custom deployment of Authorino"""
import pytest

from testsuite.openshift.objects.authorino import AuthorinoCR


@pytest.fixture(scope="session")
def authorino(openshift, blame, request, testconfig) -> AuthorinoCR:
    """Custom deployed Authorino instance"""
    if not testconfig["authorino"]["deploy"]:
        return pytest.skip("Operator tests don't work with already deployed Authorino")

    authorino = AuthorinoCR.create_instance(openshift, blame("authorino"))
    request.addfinalizer(lambda: authorino.delete(ignore_not_found=True))
    authorino.commit()
    authorino.wait_for_ready()
    return authorino
