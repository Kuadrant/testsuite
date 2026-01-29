"""Conftest for UI tests"""

import os
from pathlib import Path

import pytest
from httpx import Timeout

from testsuite.page_objects.nav_bar import NavBar
from testsuite.page_objects.navigator import Navigator


@pytest.fixture(scope="session")
def auth_state_file(browser, base_domain, testconfig, request, worker_id):
    """Login once and save authentication state (cookies, etc.) to a file for reuse"""
    # Use worker-specific state file for parallel execution
    state_file = Path(f".playwright-auth/ocp-session-{worker_id}.json")

    # Register cleanup to delete auth state after session ends
    request.addfinalizer(lambda: state_file.unlink() if state_file.exists() else None)

    if state_file.exists():
        # Auth state already exists, reuse it
        return state_file

    # Create state directory
    state_file.parent.mkdir(parents=True, exist_ok=True)

    # Create temporary context for login
    temp_context = browser.new_context(ignore_https_errors=True)
    page = temp_context.new_page()

    # Perform login
    page.goto(
        f"https://console-openshift-console.{base_domain}",
        timeout=60000,
    )
    page.locator("//a[@title='Log in with HTPasswd']").click()

    username = testconfig.get("console.username") or os.getenv("KUBE_USER", "admin")
    password = testconfig.get("console.password") or os.getenv("KUBE_PASSWORD")

    page.locator("//input[@name='username']").fill(username)
    page.locator("//input[@name='password']").fill(password)
    page.locator("//button[@type='submit']").click()

    # Wait for successful login by checking URL changed from auth page
    page.wait_for_url(f"https://console-openshift-console.{base_domain}/**", timeout=30000)

    # Give console a moment to initialize session
    page.wait_for_timeout(2000)

    # Save cookies and session storage to file
    temp_context.storage_state(path=str(state_file))

    # Cleanup browser resources
    page.close()
    temp_context.close()

    return state_file


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, auth_state_file):
    """Configure browser context to ignore HTTPS errors and load saved authentication"""
    return {
        **browser_context_args,
        "ignore_https_errors": True,
        "storage_state": str(auth_state_file),  # Load cookies/session from file
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
def navigate_console(page, base_domain, skip_or_fail):
    """Navigate to the OpenShift console and verify the console plugin is enabled"""
    page.goto(
        f"https://console-openshift-console.{base_domain}",
        timeout=60000,  # OpenShift console can be slow to fully load
    )

    navbar = NavBar(page)
    try:
        # Wait for console plugin to be visible
        navbar.kuadrant_nav.wait_for(state="visible", timeout=30000)
    except Exception:  # pylint: disable=broad-exception-caught
        skip_or_fail(
            "Kuadrant console plugin is not enabled. "
            "Please enable it via Helm charts or OpenShift console before running UI tests."
        )
    return navbar


@pytest.fixture
def navigator(page):
    """Return a Navigator bound to the current Playwright page"""
    return Navigator(page)
