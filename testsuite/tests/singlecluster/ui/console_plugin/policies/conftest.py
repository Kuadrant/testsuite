"""Conftest for Policies page UI tests"""

import os

import pytest

from testsuite.page_objects.nav_bar import NavBar
from testsuite.page_objects.navigator import Navigator


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context to ignore HTTPS certificate errors"""
    return {
        **browser_context_args,
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="module", autouse=True)
def commit():
    """Skip parent commit of auth/rate limit"""
    return None


@pytest.fixture(autouse=True)
def login(page, base_domain, testconfig):
    """Log into the OpenShift console using HTPasswd credentials"""
    page.goto(
        f"https://console-openshift-console.{base_domain}",
        timeout=60000,  # OpenShift console can be slow to fully load
    )
    page.locator("//a[@title='Log in with HTPasswd']").click()

    # Get credentials from configuration or environment variables (for nightly pipeline)
    username = testconfig.get("console.username") or os.getenv("KUBE_USER", "admin")
    password = testconfig.get("console.password") or os.getenv("KUBE_PASSWORD")

    page.locator("//input[@name='username']").fill(username)
    page.locator("//input[@name='password']").fill(password)
    page.locator("//button[@type='submit']").click()
    return NavBar(page)


@pytest.fixture(autouse=True)
def dynamic_plugin(login, skip_or_fail):
    """Verify the console plugin is enabled"""
    if not login.kuadrant_nav.is_visible:
        skip_or_fail(
            "Kuadrant console plugin is not enabled. "
            "Please enable it via Helm charts or OpenShift console before running UI tests."
        )


@pytest.fixture
def navigator(page):
    """Return a Navigator bound to the current Playwright page"""
    return Navigator(page)
