"""Conftest for UI tests"""

import os
import tempfile

import pytest
from httpx import Timeout

from testsuite.gateway.exposers import OpenShiftExposer
from testsuite.page_objects.nav_bar import NavBar
from testsuite.page_objects.navigator import Navigator


@pytest.fixture(scope="session")
def auth_state_file(browser, cluster, testconfig, request):
    """Login once and save authentication state (cookies, etc.) to a file for reuse"""
    # Create temporary file for auth state
    state_file = tempfile.NamedTemporaryFile()  # pylint: disable=consider-using-with

    # Register cleanup to close and auto-delete file after session ends
    request.addfinalizer(state_file.close)

    # Create temporary context for login
    temp_context = browser.new_context(ignore_https_errors=True)
    page = temp_context.new_page()

    # Perform login
    page.goto(cluster.console_url, timeout=60000)
    page.locator("//a[@title='Log in with HTPasswd']").click()

    username = testconfig.get("console.username") or os.getenv("KUBE_USER", "admin")
    password = testconfig.get("console.password") or os.getenv("KUBE_PASSWORD")

    page.locator("//input[@name='username']").fill(username)
    page.locator("//input[@name='password']").fill(password)
    page.locator("//button[@type='submit']").click()

    # Wait for successful login by checking URL changed from auth page
    page.wait_for_url(f"{cluster.console_url}/**", timeout=30000)

    # Give console a moment to initialize session
    page.wait_for_timeout(2000)

    # Save cookies and session storage to file
    temp_context.storage_state(path=state_file.name)

    # Cleanup browser resources
    page.close()
    temp_context.close()

    return state_file.name


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, auth_state_file):
    """Configure browser context to load saved authentication"""
    return {
        **browser_context_args,
        "storage_state": auth_state_file,  # Load cookies/session from file
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="module", autouse=True)
def commit():
    """Skip parent commit of auth/rate limit"""
    return None


@pytest.fixture(scope="module")
def client(route, hostname):  # pylint: disable=unused-argument
    """Returns httpx client with increased timeout"""
    client = hostname.client(timeout=Timeout(connect=30.0, read=10.0, write=10.0, pool=10.0))
    yield client
    client.close()


@pytest.fixture(autouse=True)
def navigate_console(page, exposer, cluster, skip_or_fail):
    """Navigate to OpenShift console and verify console plugin is enabled and visible"""
    if not isinstance(exposer, OpenShiftExposer):
        pytest.skip("UI tests require OpenShift exposer (OpenShift console not available)")

    # Check if console plugin resource exists in cluster
    plugin_check = cluster.do_action("get", "consoleplugin", "kuadrant-console-plugin", auto_raise=False)
    if plugin_check.status() != 0:
        skip_or_fail(
            "Kuadrant console plugin resource not found. Please install it via Helm charts before running UI tests."
        )

    # Check if plugin is enabled in console operator
    console_config = cluster.do_action(
        "get", "console.operator.openshift.io", "cluster", "-o", "jsonpath={.spec.plugins}", auto_raise=False
    )
    if console_config.status() == 0 and "kuadrant-console-plugin" not in console_config.out():
        skip_or_fail(
            "Kuadrant console plugin is installed but not enabled. "
            "Please enable it in the console operator configuration."
        )

    page.goto(cluster.console_url, timeout=60000)  # OpenShift console can be slow to fully load

    # Wait for console plugin nav element (plugin is enabled at this point, so should be available)
    NavBar(page).kuadrant_nav.wait_for(state="visible", timeout=30000)


@pytest.fixture
def navigator(page):
    """Return a Navigator bound to the current Playwright page"""
    return Navigator(page)
