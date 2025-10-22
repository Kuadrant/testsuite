"""Conftest for rate limit tests"""

import pytest

# Configure which components to collect logs from when tests fail
# Available components: authorino, limitador, gateway, dns-operator, authorino-operator, kuadrant-operator
# If not specified, all available components will be logged
log_components = ["limitador", "limitador-operator", "gateway"]

@pytest.fixture(scope="session")
def limitador(kuadrant):
    """Returns Limitador CR"""

    return kuadrant.limitador


@pytest.fixture(scope="module", autouse=True)
def commit(request, rate_limit):
    """Commits all important stuff before tests"""
    request.addfinalizer(rate_limit.delete)
    rate_limit.commit()
    rate_limit.wait_for_ready()
