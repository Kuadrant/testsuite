"""Root conftest"""
import signal

import pytest
from dynaconf import ValidationError
from keycloak import KeycloakAuthenticationError
from weakget import weakget

from testsuite.mockserver import Mockserver
from testsuite.oidc import OIDCProvider
from testsuite.config import settings
from testsuite.oidc.auth0 import Auth0Provider
from testsuite.openshift.httpbin import Httpbin
from testsuite.openshift.envoy import Envoy
from testsuite.oidc.rhsso import RHSSO
from testsuite.openshift.objects.gateway_api import Gateway
from testsuite.openshift.objects.proxy import Proxy
from testsuite.utils import randomize, _whoami


def pytest_addoption(parser):
    """Add options to include various kinds of tests in testrun"""
    parser.addoption(
        "--performance", action="store_true", default=False, help="Run also performance tests (default: False)"
    )
    parser.addoption("--glbc", action="store_true", default=False, help="Run also glbc tests (default: False)")


def pytest_runtest_setup(item):
    """Exclude performance tests by default, require explicit option"""
    marks = [i.name for i in item.iter_markers()]
    if "performance" in marks and not item.config.getoption("--performance"):
        pytest.skip("Excluding performance tests")
    if "glbc" in marks and not item.config.getoption("--glbc"):
        pytest.skip("Excluding glbc tests")


@pytest.fixture(scope="session", autouse=True)
def term_handler():
    """
    This will handle ^C, cleanup won't be skipped
    https://github.com/pytest-dev/pytest/issues/9142
    """
    orig = signal.signal(signal.SIGTERM, signal.getsignal(signal.SIGINT))
    yield
    signal.signal(signal.SIGTERM, orig)


# pylint: disable=unused-argument
def pytest_collection_modifyitems(session, config, items):
    """
    Add user properties to testcases for xml output

    This adds issue and issue-id properties to junit output, utilizes
    pytest.mark.issue marker.

    This is copied from pytest examples to record custom properties in junit
    https://docs.pytest.org/en/stable/usage.html
    """

    for item in items:
        for marker in item.iter_markers(name="issue"):
            issue = marker.args[0]
            item.user_properties.append(("issue", issue))


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
        info = RHSSO(
            cnf["url"],
            cnf["username"],
            cnf["password"],
            blame("realm"),
            blame("client"),
            cnf["test_user"]["username"],
            cnf["test_user"]["password"],
        )

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
def kuadrant(testconfig, openshift):
    """Returns Kuadrant instance if exists, or None"""
    settings = weakget(testconfig)
    try:
        if not settings["kuadrant"]["enabled"] % True:
            return None

        # Try if Kuadrant is deployed
        kuadrant_openshift = openshift.change_project(settings["kuadrant"]["project"] % None)
        kuadrants = kuadrant_openshift.do_action("get", "kuadrant", "-o", "json", parse_output=True)
        assert len(kuadrants.model["items"]) > 0

        # Try if the configured Gateway is deployed
        gateway_openshift = openshift.change_project(settings["kuadrant"]["gateway"]["project"] % None)
        name = testconfig["kuadrant"]["gateway"]["name"]
        gateway_openshift.do_action("get", f"Gateway/{name}")

        # TODO: Return actual Kuadrant object
        return True
    # pylint: disable=broad-except
    except Exception:
        return None


@pytest.fixture(scope="session")
def backend(request, openshift, blame, label):
    """Deploys Httpbin backend"""
    httpbin = Httpbin(openshift, blame("httpbin"), label)
    request.addfinalizer(httpbin.delete)
    httpbin.commit()
    return httpbin


@pytest.fixture(scope="module")
def envoy(request, kuadrant, authorino, openshift, blame, backend, module_label, testconfig) -> Proxy:
    """Deploys Envoy that wire up the Backend behind the reverse-proxy and Authorino instance"""
    if kuadrant:
        envoy: Proxy = Gateway(openshift, "istio-ingressgateway", "istio-system", module_label, backend)
    else:
        envoy = Envoy(openshift, authorino, blame("envoy"), module_label, backend, testconfig["envoy"]["image"])
    request.addfinalizer(envoy.delete)
    envoy.commit()
    return envoy


@pytest.fixture(scope="session")
def wildcard_domain(openshift):
    """
    Wildcard domain of openshift cluster
    """
    return f"*.{openshift.apps_url}"
