"""Root conftest"""
import signal

from urllib.parse import urlparse

import pytest
from dynaconf import ValidationError
from keycloak import KeycloakAuthenticationError

from testsuite.mockserver import Mockserver
from testsuite.oidc import OIDCProvider
from testsuite.config import settings
from testsuite.oidc.auth0 import Auth0Provider
from testsuite.openshift.httpbin import Httpbin
from testsuite.openshift.envoy import Envoy
from testsuite.oidc.rhsso import RHSSO
from testsuite.utils import randomize, _whoami


@pytest.fixture(scope='session', autouse=True)
def term_handler():
    """
    This will handle ^C, cleanup won't be skipped
    https://github.com/pytest-dev/pytest/issues/9142
    """
    orig = signal.signal(signal.SIGTERM, signal.getsignal(signal.SIGINT))
    yield
    signal.signal(signal.SIGTERM, orig)


@pytest.fixture(scope="session")
def testconfig():
    """Testsuite settings"""
    return settings


@pytest.fixture(scope="session")
def openshift(testconfig):
    """OpenShift client for the primary namespace"""
    client = testconfig["openshift"]
    if not client.connected:
        pytest.fail("You are not logged into Openshift or the namespace doesn't exist")
    return client


@pytest.fixture(scope="session")
def openshift2(testconfig):
    """OpenShift client for the secondary namespace located on the same cluster as primary Openshift"""
    client = testconfig["openshift2"]
    if client is None:
        pytest.skip("Openshift2 required but second_project was not set")
    if not client.connected:
        pytest.fail("You are not logged into Openshift or the namespace for Openshift2 doesn't exist")
    return client


@pytest.fixture(scope="session")
def kcp(testconfig):
    """Modified OpenShift client acting as Kcp client"""
    client = testconfig["kcp"]
    if client is None:
        pytest.skip("Kcp required but was not configured")

    # does not work for kcp yet
    # internally implemented using `oc status` command that seems internally touching project kind
    # that is not available on kcp
    # if not client.connected:
    #     pytest.fail("You are not logged into Openshift or the namespace for Kcp doesn't exist")

    return client


@pytest.fixture(scope="session")
def rhsso(request, testconfig, blame):
    """RHSSO OIDC Provider fixture"""
    try:
        testconfig.validators.validate(only="rhsso")
        cnf = testconfig["rhsso"]
        info = RHSSO(cnf["url"], cnf["username"], cnf["password"], blame("realm"), blame("client"),
                     cnf["test_user"]["username"], cnf["test_user"]["password"])

        if not testconfig["skip_cleanup"]:
            request.addfinalizer(info.delete)

        info.commit()
        return info
    except KeycloakAuthenticationError:
        return pytest.skip("Unable to login into SSO, please check the credentials provided")
    except KeyError as exc:
        return pytest.skip(f"SSO configuration item is missing: {exc}")


@pytest.fixture(scope="session")
def auth0(testconfig):
    """Auth0 OIDC provider fixture"""
    try:
        section = testconfig["auth0"]
        return Auth0Provider(section["url"], section["client_id"], section["client_secret"])
    except KeyError as exc:
        return pytest.skip(f"Auth0 configuration item is missing: {exc}")


@pytest.fixture(scope="module")
def mockserver(testconfig):
    """Returns mockserver"""
    try:
        testconfig.validators.validate(only=["mockserver"])
        return Mockserver(testconfig["mockserver"]["url"])
    except (KeyError, ValidationError) as exc:
        return pytest.skip(f"Mockserver configuration item is missing: {exc}")


@pytest.fixture(scope="session")
def oidc_provider(rhsso) -> OIDCProvider:
    """Fixture which enables switching out OIDC providers for individual modules"""
    return rhsso


@pytest.fixture(scope="session")
def blame(request):
    """Returns function that will add random identifier to the name"""
    def _blame(name: str, tail: int = 3) -> str:
        """Create 'scoped' name within given test

        This returns unique name for object(s) to avoid conflicts

        Args:
            :param name: Base name, e.g. 'svc'
            :param tail: length of random suffix"""

        nodename = request.node.name
        if nodename.startswith("test_"):  # is this always true?
            nodename = nodename[5:]

        context = nodename.lower().split("_")[0]
        if len(context) > 2:
            context = context[:2] + context[2:-1].translate(str.maketrans("", "", "aiyu")) + context[-1]

        if "." in context:
            context = context.split(".")[0]

        return randomize(f"{name[:8]}-{_whoami()[:8]}-{context[:9]}", tail=tail)
    return _blame


@pytest.fixture(scope="session")
def label(blame):
    """Session scope label for all resources"""
    return blame("testrun")


@pytest.fixture(scope="module")
def module_label(label):
    """Module scope label for all resources"""
    return randomize(label)


@pytest.fixture(scope="session")
def backend(request, openshift, blame, label):
    """Deploys Httpbin backend"""
    httpbin = Httpbin(openshift, blame("httpbin"), label)
    request.addfinalizer(httpbin.delete)
    httpbin.commit()
    return httpbin


@pytest.fixture(scope="module")
def envoy(request, authorino, openshift, blame, backend, module_label, testconfig):
    """Deploys Envoy that wire up the Backend behind the reverse-proxy and Authorino instance"""
    envoy = Envoy(openshift, authorino, blame("envoy"), module_label, backend.url, testconfig["envoy"]["image"])
    request.addfinalizer(envoy.delete)
    envoy.commit()
    return envoy


@pytest.fixture(scope="session")
def wildcard_domain(openshift):
    """
    Wildcard domain of openshift cluster
    """
    hostname = urlparse(openshift.api_url).hostname
    return "*.apps." + hostname.split(".", 1)[1]
