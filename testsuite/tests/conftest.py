"""Root conftest"""

import operator
import signal
from urllib.parse import urlparse

import yaml
import pytest
from pytest_metadata.plugin import metadata_key  # type: ignore
from dynaconf import ValidationError
from keycloak import KeycloakAuthenticationError
from openshift_client import selector

from testsuite.capabilities import has_kuadrant, kuadrant_version
from testsuite.certificates import CFSSLClient
from testsuite.config import settings
from testsuite.gateway import Exposer, CustomReference
from testsuite.httpx import KuadrantClient
from testsuite.mockserver import Mockserver
from testsuite.oidc import OIDCProvider
from testsuite.oidc.auth0 import Auth0Provider
from testsuite.prometheus import Prometheus
from testsuite.oidc.keycloak import Keycloak
from testsuite.tracing.jaeger import JaegerClient
from testsuite.kubernetes.config_map import ConfigMap
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
    # prevents ERROR OpenShiftPythonException due to oc and kuadrant not being set-up
    # when just printing setup plan
    # error is raised during has_kuadrant()
    if item.config.getoption("--setup-plan"):
        return
    marks = [i.name for i in item.iter_markers()]
    skip_or_fail = pytest.fail if item.config.getoption("--enforce") else pytest.skip
    standalone = item.config.getoption("--standalone")
    if standalone:
        if "authorino" not in marks:
            skip_or_fail("Only Authorino tests are supported in Standalone mode currently")
        if "kuadrant_only" in marks:
            skip_or_fail("This test can run as a part of the Kuadrant only, please remove --standalone flag")
    else:
        if "standalone_only" in marks:
            skip_or_fail(
                "Unable to run Standalone only test: Standalone mode is disabled, please use --standalone flag"
            )
        kuadrant, error = has_kuadrant()
        if not kuadrant:
            skip_or_fail(f"Unable to locate Kuadrant installation: {error}")


def _format_failure_message(call, report):
    """Extract failure message from call/report, keeping only testsuite frames."""
    if not call.excinfo:
        return str(report.longrepr or "")
    tb_lines = []
    for entry in call.excinfo.traceback:
        if "site-packages" not in str(entry.path):
            tb_lines.append(f"{entry.path}:{entry.lineno}: in {entry.name}\n    {entry.statement}")

    exc = call.excinfo.value
    exc_message = str(exc)
    # OpenShiftPythonException embeds full K8s objects in its message;
    # extract just the stderr from each action
    result = getattr(exc, "result", None)
    if result is not None and callable(getattr(result, "actions", None)):
        errs = [a.err.strip() for a in result.actions() if getattr(a, "err", None)]
        if errs:
            exc_message = "; ".join(errs)

    tb_lines.append(f"E   {call.excinfo.type.__name__}: {exc_message}")
    return "\n".join(tb_lines)


def _collect_rerun_attempt(item, call, report):
    """Record failure message and captured output for one rerun attempt."""
    message = _format_failure_message(call, report)
    if report.failed and call.excinfo:
        exc = call.excinfo.value
        result = getattr(exc, "result", None)
        if result is not None and callable(getattr(result, "actions", None)):
            report.longrepr = message
    item.rerun_messages = getattr(item, "rerun_messages", []) + [message]

    captured_output = "".join(content for _, content in report.sections if content)
    item.rerun_outputs = getattr(item, "rerun_outputs", []) + [captured_output]


def _write_rerun_properties(item, report):
    """Write collected rerun data into JUnit XML user properties at teardown."""
    execution_count = getattr(item, "execution_count", 1)
    if execution_count > 1:
        rerun_messages = getattr(item, "rerun_messages", [])
        rerun_outputs = getattr(item, "rerun_outputs", [])
        report.user_properties.append(("__rp_reruns", str(execution_count - 1)))
        for i, msg in enumerate(rerun_messages, start=1):
            report.user_properties.append((f"__rp_rerun_{i}_message", msg))
        for i, output in enumerate(rerun_outputs, start=1):
            if output:
                report.user_properties.append((f"__rp_rerun_{i}_output", output))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Add jira link to html report and record rerun count for JUnit XML."""
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
    if report.when in ("call", "setup") and (report.failed or report.outcome == "rerun"):
        _collect_rerun_attempt(item, call, report)
    if report.when == "teardown":
        _write_rerun_properties(item, report)


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


def _detect_gateway_api_version():
    """Detect Gateway API CRD version from the cluster at collection time"""
    try:
        cluster = settings["control_plane"]["cluster"].change_project(settings["service_protection"]["project"])
    except (KeyError, ValidationError):
        return None

    with cluster.context:
        if (crd := selector("crd/gateways.gateway.networking.k8s.io").object(ignore_not_found=True)) is None:
            return None

    if (version_str := crd.model.metadata.annotations.get("gateway.networking.k8s.io/bundle-version")) is None:
        return None
    return tuple(int(p) for p in str(version_str).removeprefix("v").split(".")[:3])


def pytest_collection_modifyitems(session, config, items):  # pylint: disable=unused-argument
    """
    Add user properties to testcases for xml output

    This adds issue properties to junit output, utilizes
    pytest.mark.issue marker.

    This is copied from pytest examples to record custom properties in junit
    https://docs.pytest.org/en/stable/usage.html
    """

    for item in items:
        for marker in item.iter_markers(name="issue"):
            if marker.args:
                item.user_properties.append(("issue", marker.args[0]))

        ## extracting test's docstring for RP
        func = getattr(item, "function", None)
        if func and func.__doc__:
            item.user_properties.append(("__rp_case_description", func.__doc__))

    gateway_api_ver = _detect_gateway_api_version()
    for item in items:
        marker = item.get_closest_marker("gateway_api_version")
        if marker:
            required = marker.args[0]
            op = marker.args[1] if len(marker.args) > 1 else operator.ge
            if gateway_api_ver is None or not op(gateway_api_ver, required):
                got = f"v{'.'.join(map(str, gateway_api_ver))}" if gateway_api_ver else "unknown"
                item.add_marker(
                    pytest.mark.skip(
                        reason=f"Requires Gateway API CRDs {op.__name__} v{'.'.join(map(str, required))}, got {got}"
                    )
                )


@pytest.fixture(scope="session")
def testconfig():
    """Testsuite settings"""
    return settings


@pytest.fixture(scope="session")
def prometheus(cluster):
    """
    Return an instance of Thanos metrics client
    Skip tests if query route is not properly configured
    """
    openshift_monitoring = cluster.change_project("openshift-monitoring")
    # Check if metrics are enabled
    try:
        with openshift_monitoring.context:
            cm = selector("cm/cluster-monitoring-config").object(cls=ConfigMap)
            assert yaml.safe_load(cm["config.yaml"])["enableUserWorkload"]
    except Exception:  # pylint: disable=broad-exception-caught
        pytest.skip("User workload monitoring is disabled")

    # find thanos-querier route in the openshift-monitoring project
    # this route allows to query metrics

    routes = openshift_monitoring.get_routes_for_service("thanos-querier")
    if len(routes) == 0:
        pytest.skip("Skipping metrics tests as query route is not properly configured")

    url = ("https://" if "tls" in routes[0].model.spec else "http://") + routes[0].model.spec.host
    with KuadrantClient(headers={"Authorization": f"Bearer {cluster.token}"}, base_url=url, verify=False) as client:
        yield Prometheus(client)


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
def system_project(testconfig, cluster):
    """Kubernetes client for the Kuadrant system namespace"""
    return cluster.change_project(testconfig["service_protection"]["system_project"])


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


@pytest.fixture(scope="session")
def openshift_version(cluster):
    """Get OpenShift cluster version"""
    result = cluster.do_action(
        "get", "clusterversion", "version", "-o", "jsonpath={.status.desired.version}", auto_raise=False
    )
    if result.status() != 0:
        return None
    version_str = result.out().strip()
    parts = version_str.split(".")
    return tuple(int(p.split("-")[0]) for p in parts[:2])  # Convert "4.20.0" -> (4, 20)


@pytest.fixture(autouse=True)
def check_min_ocp_version(request, openshift_version):
    """Skip tests marked with @pytest.mark.min_ocp_version if OCP version is below required"""
    marker = request.node.get_closest_marker("min_ocp_version")
    if marker:
        required_version = marker.args[0]
        if openshift_version is None:
            pytest.skip("Could not detect OpenShift version")
        if openshift_version < required_version:
            pytest.skip(f"Requires OCP {'.'.join(map(str, required_version))}+")
