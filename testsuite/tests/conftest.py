"""Root conftest"""

import signal
from urllib.parse import urlparse

import pytest
from pytest_metadata.plugin import metadata_key  # type: ignore
from dynaconf import ValidationError
from keycloak import KeycloakAuthenticationError

from testsuite.capabilities import has_kuadrant, kuadrant_version
from testsuite.certificates import CFSSLClient
from testsuite.config import settings
from testsuite.gateway import Exposer, CustomReference
from testsuite.httpx import KuadrantClient
from testsuite.mockserver import Mockserver
from testsuite.oidc import OIDCProvider
from testsuite.oidc.auth0 import Auth0Provider
from testsuite.oidc.keycloak import Keycloak
from testsuite.tracing.jaeger import JaegerClient
from testsuite.tracing.tempo import RemoteTempoClient
from testsuite.utils import randomize, _whoami


def pytest_addoption(parser):
    """Add options to include various kinds of tests in testrun"""
    parser.addoption(
        "--enforce", action="store_true", default=False, help="Fails tests instead of skip, if capabilities are missing"
    )
    parser.addoption("--standalone", action="store_true", default=False, help="Runs testsuite in standalone mode")


def pytest_runtest_setup(item):
    """
    Skip or fail tests based on available capabilities and marks
    First round of filtering is usually done by pytest through -m option
    (https://docs.pytest.org/en/latest/example/markers.html#marking-test-functions-and-selecting-them-for-a-run)
    In this function we skip or fail the tests that were selected but their capabilities are not available
    """
    marks = [i.name for i in item.iter_markers()]
    skip_or_fail = pytest.fail if item.config.getoption("--enforce") else pytest.skip
    standalone = item.config.getoption("--standalone")
    if standalone:
        if "kuadrant_only" in marks:
            skip_or_fail("Unable to run Kuadrant Only tests: Standalone mode is enabled")
    else:
        if "standalone_only" in marks:
            skip_or_fail(
                "Unable to run Standalone only test: Standalone mode is disabled, please use --standalone flag"
            )
        kuadrant, error = has_kuadrant()
        if not kuadrant:
            skip_or_fail(f"Unable to locate Kuadrant installation: {error}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):  # pylint: disable=unused-argument
    """Add jira link to html report"""
    pytest_html = item.config.pluginmanager.getplugin("html")
    outcome = yield
    report = outcome.get_result()
    extra = getattr(report, "extra", [])
    if report.when == "setup":
        for marker in item.iter_markers(name="issue"):
            issue = marker.args[0]
            url = urlparse(issue)
            if "github" in url.hostname:
                label = url.path.replace("/issues/", "#")[1:]
            else:
                label = issue
            extra.append(pytest_html.extras.url(issue, name=label))
        report.extra = extra


def pytest_report_header(config):
    """Adds Kuadrant version string to pytest header output for every cluster."""
    header = ""
    images = []
    for image, cluster in kuadrant_version():
        header += f"Kuadrant image: {image} on cluster {cluster}\n"
        images.append(image)
    config.stash[metadata_key]["Kuadrant"] = images
    return header


@pytest.fixture(scope="session")
def skip_or_fail(request):
    """Skips or fails tests depending on --enforce option"""
    return pytest.fail if request.config.getoption("--enforce") else pytest.skip


@pytest.fixture(scope="session", autouse=True)
def term_handler():
    """
    This will handle ^C, cleanup won't be skipped
    https://github.com/pytest-dev/pytest/issues/9142
    """
    orig = signal.signal(signal.SIGTERM, signal.getsignal(signal.SIGINT))
    yield
    signal.signal(signal.SIGTERM, orig)


def pytest_collection_modifyitems(session, config, items):  # pylint: disable=unused-argument
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
def keycloak(request, testconfig, blame, skip_or_fail):
    """Keycloak OIDC Provider fixture"""
    try:
        testconfig.validators.validate(only="keycloak")
        cnf = testconfig["keycloak"]
        info = Keycloak(
            cnf["url"],
            cnf["username"],
            cnf["password"],
            blame("realm"),
            "base-client",
            cnf["test_user"]["username"],
            cnf["test_user"]["password"],
        )
        request.addfinalizer(info.delete)
        info.commit()
        return info
    except KeycloakAuthenticationError:
        return skip_or_fail("Unable to login into SSO, please check the credentials provided")
    except KeyError as exc:
        return skip_or_fail(f"SSO configuration item is missing: {exc}")


@pytest.fixture(scope="session")
def auth0(testconfig):
    """Auth0 OIDC provider fixture"""
    try:
        section = testconfig["auth0"]
        return Auth0Provider(section["url"], section["client_id"], section["client_secret"])
    except KeyError as exc:
        return pytest.skip(f"Auth0 configuration item is missing: {exc}")


@pytest.fixture(scope="session")
def cfssl(testconfig, skip_or_fail):
    """CFSSL client library"""
    client = CFSSLClient(binary=testconfig["cfssl"])
    if not client.exists:
        skip_or_fail("Skipping CFSSL tests as CFSSL binary path is not properly configured")
    return client


@pytest.fixture(scope="session")
def mockserver(testconfig, skip_or_fail):
    """Returns mockserver"""
    try:
        testconfig.validators.validate(only=["mockserver"])
    except (KeyError, ValidationError) as exc:
        skip_or_fail(f"Mockserver configuration item is missing: {exc}")

    with KuadrantClient(base_url=testconfig["mockserver"]["url"]) as client:
        yield Mockserver(client)


@pytest.fixture(scope="session")
def tracing(testconfig, skip_or_fail):
    """Returns tracing client for tracing tests"""
    try:
        testconfig.validators.validate(only=["tracing"])
    except (KeyError, ValidationError) as exc:
        skip_or_fail(f"Tracing configuration item is missing: {exc}")

    cls = JaegerClient if testconfig["tracing"]["backend"] == "jaeger" else RemoteTempoClient
    # Authorino needs to have verify disabled because it doesn't trust local service URLs
    with KuadrantClient(verify=False) as client:
        yield cls(
            testconfig["tracing"]["collector_url"],
            testconfig["tracing"]["query_url"],
            client,
        )


@pytest.fixture(scope="session")
def oidc_provider(keycloak) -> OIDCProvider:
    """Fixture which enables switching out OIDC providers for individual modules"""
    return keycloak


@pytest.fixture(scope="session")
def blame(request):
    """Returns function that will add random identifier to the name"""
    if "tester" in settings:
        user = settings["tester"]
    else:
        user = _whoami()

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

        return randomize(f"{name[:8]}-{user[:8]}-{context[:9]}", tail=tail)

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
def cluster(testconfig):
    """Kubernetes client for the primary namespace"""
    project = testconfig["service_protection"]["project"]
    client = testconfig["control_plane"]["cluster"].change_project(project)
    if not client.connected:
        pytest.fail(f"You are not logged into Kubernetes or the {project} namespace doesn't exist")
    return client


@pytest.fixture(scope="session")
def exposer(request, testconfig, cluster) -> Exposer:
    """Exposer object instance"""
    exposer = testconfig["default_exposer"](cluster)
    request.addfinalizer(exposer.delete)
    exposer.commit()
    return exposer


@pytest.fixture(scope="session")
def base_domain(exposer):
    """Returns preconfigured base domain"""
    return exposer.base_domain


@pytest.fixture(scope="session")
def wildcard_domain(base_domain):
    """Wildcard domain"""
    return f"*.{base_domain}"


@pytest.fixture(scope="session")
def cluster_issuer(testconfig):
    """Reference to cluster self-signed certificate issuer"""
    return CustomReference(
        group="cert-manager.io",
        kind=testconfig["control_plane"]["issuer"]["kind"],
        name=testconfig["control_plane"]["issuer"]["name"],
    )


@pytest.fixture(scope="session")
def dns_provider_secret(testconfig):
    """Contains name of DNS provider secret"""
    return testconfig["control_plane"]["provider_secret"]
