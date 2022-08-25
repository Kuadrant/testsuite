"""Conftest for all tests requiring custom deployment of Authorino"""
from urllib.parse import urlparse

import pytest
from weakget import weakget

from testsuite.openshift.objects.authorino import AuthorinoCR


@pytest.fixture(scope="module")
def authorino_parameters():
    """Optional parameters for Authorino creation, passed to the __init__"""
    return {}


@pytest.fixture(scope="module")
def cluster_wide():
    """True, if Authorino should be deployed in cluster-wide setup"""
    return False


@pytest.fixture(scope="module")
def authorino(openshift, blame, request, testconfig, cluster_wide, module_label, authorino_parameters) -> AuthorinoCR:
    """Custom deployed Authorino instance"""
    if not testconfig["authorino"]["deploy"]:
        return pytest.skip("Operator tests don't work with already deployed Authorino")

    if authorino_parameters.get("label_selectors"):
        authorino_parameters["label_selectors"].append(f"testRun={module_label}")
    else:
        authorino_parameters["label_selectors"] = [f"testRun={module_label}"]

    authorino = AuthorinoCR.create_instance(openshift,
                                            blame("authorino"),
                                            cluster_wide=cluster_wide,
                                            image=weakget(testconfig)["authorino"]["image"] % None,
                                            **authorino_parameters)
    request.addfinalizer(lambda: authorino.delete(ignore_not_found=True))
    authorino.commit()
    authorino.wait_for_ready()
    return authorino


@pytest.fixture(scope="session")
def wildcard_domain(openshift):
    """
    Wildcard domain of openshift cluster
    """
    hostname = urlparse(openshift.api_url).hostname
    return "*.apps." + hostname.split(".", 1)[1]
