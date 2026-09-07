"""Root conftest"""

import logging
import operator
import signal
from datetime import datetime
from urllib.parse import urlparse

import pytest
from openshift_client import selector
from pytest_metadata.plugin import metadata_key  # type: ignore
from dynaconf import Dynaconf, ValidationError
from keycloak import KeycloakAuthenticationError

from testsuite.capabilities import has_kuadrant, kuadrant_version
from testsuite.certificates import CFSSLClient
from testsuite.config import settings
from testsuite.gateway import Exposer, CustomReference
from testsuite.gateway.gateway_api.gateway import KuadrantGateway
from testsuite.httpx import KuadrantClient
from testsuite.mockserver import Mockserver
from testsuite.oidc import OIDCProvider
from testsuite.oidc.auth0 import Auth0Provider
from testsuite.prometheus import Prometheus
from testsuite.oidc.keycloak import Keycloak
from testsuite.tracing.jaeger import JaegerClient
from testsuite.tracing.tempo import RemoteTempoClient
from testsuite.utils import randomize, _whoami
from testsuite.utils import resource_collector

logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    """Add options to include various kinds of tests in testrun"""
    parser.addoption(
        "--enforce", action="store_true", default=False, help="Fails tests instead of skip, if capabilities are missing"
    )
    parser.addoption("--standalone", action="store_true", default=False, help="Runs testsuite in standalone mode")
    parser.addoption(
        "--verify-denials", default="true", help="Verifies that denied requests did not leak to the upstream backend"
    )
    parser.addoption(
        "--collect-resources",
        action="store_true",
        default=False,
        help="Collect and save all test resources to debug-resources/ (or $WORKSPACE/debug-resources/)",
    )
    parser.addoption(
        "--collect-resources-on-failure",
        action="store_true",
        default=False,
        help="Collect and save test resources only for failed tests",
    )


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

    if item.fspath.basename == "info_collector.py":
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
    """Add jira link to html report, record rerun count, and collect cluster resources."""
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
    _try_collect_resources(item, report)


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
def prometheus(cluster, testconfig, skip_or_fail):
    """Prometheus metrics client, auto-discovered via DefaultValueValidator or configured explicitly"""
    try:
        testconfig.validators.validate(only=["prometheus"])
        url = testconfig["prometheus"]["url"]
    except (KeyError, ValidationError):
        skip_or_fail(
            "Prometheus not available. Set prometheus.project and prometheus.service for your environment, "
            "or override with prometheus.url in config."
        )
        return

    headers = {}
    if url.startswith("https"):
        headers["Authorization"] = f"Bearer {cluster.token}"

    with KuadrantClient(headers=headers, base_url=url, verify=False) as client:
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
def module_label(label, request):
    """Module scope label for all resources"""
    value = randomize(label)
    request.node.resource_collection_module_label = value
    return value


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
def openshift_version(testconfig):
    """Get OpenShift cluster version"""
    cluster = testconfig["control_plane"]["cluster"]
    version = cluster.ocp_version
    if version is None:
        return None
    parts = version.split(".")
    return tuple(int(p.split("-")[0]) for p in parts[:2])  # Convert "4.20" -> (4, 20)


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


def _is_multicluster_test(item: pytest.Item) -> bool:
    """Check if test is a multicluster test by looking at its path."""
    if "multicluster" in str(getattr(item, "fspath", "")):
        return True
    return "multicluster" in getattr(item, "nodeid", "")


def _extract_base_pattern(module_label: str) -> str:
    """Extract session part of module_label (testrun-<user>--<sess>) for matching."""
    base_pattern = module_label
    if "--" in module_label:
        prefix, suffix = module_label.split("--", 1)
        base_pattern = f"{prefix}--{suffix.split('-')[0]}"
    return base_pattern


def _get_clusters(item: pytest.Item, testconfig) -> list[tuple[str, object]]:
    """Get cluster clients for this test (single-cluster or multicluster)."""
    clusters = [("cluster1", testconfig["control_plane"]["cluster"])]
    if _is_multicluster_test(item):
        for name in ("cluster2", "cluster3"):
            client = testconfig["control_plane"].get(name)
            if client:
                clusters.append((name, client))
    return clusters


def _nodeid_filename_fragment(nodeid: str) -> str:
    """Unique YAML filename fragment from a pytest nodeid / RP item name.

    Includes the last three path components so two files with the same basename
    in different directories do not collide. Must stay in sync with
    reportportal.rp_attach.filename_needle_from_rp_name.
    """
    path_part, sep, test_part = nodeid.partition("::")
    if not sep:
        test_part = path_part.rsplit("/", 1)[-1]
    if path_part.endswith(".py"):
        path_part = path_part[:-3]
    unique_module = "_".join(path_part.split("/")[-3:])
    name = f"{unique_module}_{test_part}"
    return name.replace("[", "(").replace("]", ")").replace("/", "_").replace("\\", "_")


def _safe_collection_name(item: pytest.Item, module_label: str) -> str:
    """Build a filesystem-safe base filename from the test nodeid."""
    return f"{module_label}-{_nodeid_filename_fragment(item.nodeid)}"


def _write_resource_files(matched: list, base_pattern: str, prefix: str) -> None:
    """Write the apply (reproducible) and full (with status) YAML views for the matched resources."""
    out = resource_collector.output_dir()
    full_resources = [resource_collector.strip_full(r) for r in matched]
    resource_collector.write_yaml(out / f"{prefix}-full.yaml", base_pattern, full_resources)

    apply_resources = [resource_collector.strip_apply(r) for r in matched if resource_collector.is_applyable(r)]
    resource_collector.write_yaml(out / f"{prefix}-apply.yaml", base_pattern, apply_resources)


def _do_collection(item: pytest.Item, module_label: str, base_pattern: str, project: str, clusters: list) -> None:
    """Orchestrate resource collection from clusters."""
    out = resource_collector.output_dir()
    out.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_collection_name(item, module_label)
    multicluster = len(clusters) > 1
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    for cluster_name, cluster_client in clusters:
        try:
            with cluster_client.context:
                resource_types = resource_collector.discover_resource_types()
                if not resource_types:
                    logger.warning("No resource types discovered for %s", cluster_name)
                    continue

                matched = resource_collector.collect_matching(project, base_pattern, resource_types)
                prefix = f"{safe_name}-{cluster_name}" if multicluster else safe_name
                _write_resource_files(matched, base_pattern, f"{prefix}-{timestamp}")
        except resource_collector.COLLECTION_ERRORS:
            logger.warning("Failed to collect resources from %s", cluster_name, exc_info=True)


def _should_collect_resources(item: pytest.Item, report) -> bool:
    """Whether this report phase should dump cluster resources."""
    if report.when not in ("call", "setup") or report.skipped:
        return False
    if item.config.getoption("--collect-resources"):
        # After a completed call, or when setup failed (call never runs).
        return report.when == "call" or report.failed
    if item.config.getoption("--collect-resources-on-failure"):
        # Final failures only; rerun attempts have outcome "rerun", not failed.
        return report.failed
    return False


def _get_resource_collection_ctx(item: pytest.Item) -> tuple[str, Dynaconf] | None:
    """Return (module_label, testconfig) for a resource dump.

    Never call getfixturevalue here: after failed setup the fixture stack is torn
    down and xdist raises INTERNALERROR.
    """
    if ctx := getattr(item, "resource_collection_ctx", None):
        return ctx

    module_node = item.getparent(pytest.Module)
    if module_node is None:
        return None

    module_label = getattr(module_node, "resource_collection_module_label", None)
    if module_label:
        return module_label, settings
    return None


def _try_collect_resources(item: pytest.Item, report) -> None:
    """Dump cluster resources for this test when collection is enabled."""
    if not _should_collect_resources(item, report):
        return
    if item.nodeid in resource_collector.collected_nodes:
        return

    try:
        ctx = _get_resource_collection_ctx(item)
        if ctx is None:
            logger.warning("Skipping resource collection for %s: fixtures not available", item.nodeid)
            return

        module_label, testconfig = ctx
        project = testconfig["service_protection"]["project"]
        clusters = _get_clusters(item, testconfig)
        base_pattern = _extract_base_pattern(module_label)
        _do_collection(item, module_label, base_pattern, project, clusters)
        resource_collector.collected_nodes.add(item.nodeid)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Resource collection failed for %s", item.nodeid, exc_info=True)


@pytest.fixture(scope="function", autouse=True)
def collect_test_resources(request, module_label, testconfig):
    """Stash fixtures used to dump cluster resources after the test call."""
    request.node.resource_collection_ctx = (module_label, testconfig)


@pytest.fixture(autouse=True)
def check_user_managed_istio(request, cluster, skip_or_fail):
    """Skip tests that require a user-managed Istio (e.g. mTLS, sidecar injection).
    OCP-managed Istio does not allow modifications to the Istio CR."""
    marker = request.node.get_closest_marker("user_managed_istio")
    if marker and KuadrantGateway.get_gateway_class_name(cluster) == "openshift-default":
        skip_or_fail("Test requires user-managed Istio installation")
