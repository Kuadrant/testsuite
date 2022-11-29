"""Conftest for custom Response tests"""
import pytest

from testsuite.openshift.objects.auth_config import AuthConfig


@pytest.fixture(scope="module")
def responses():
    """Returns responses to be added to the AuthConfig"""
    return []


@pytest.fixture(scope="module")
def authorization(openshift, blame, envoy, oidc_provider, responses, module_label):
    """Add response to Authorization"""
    authorization = AuthConfig.create_instance(openshift,
                                               blame("ac"),
                                               envoy.hostname,
                                               labels={"testRun": module_label})
    authorization.identity.oidc("rhsso", oidc_provider.well_known["issuer"])
    for response in responses:
        authorization.responses.add(response)
    return authorization


# pylint: disable=unused-argument
@pytest.fixture(scope="function", autouse=True)
def commit(request, authorization, responses):
    """Commits all important stuff before tests"""
    request.addfinalizer(authorization.delete)
    authorization.commit()
