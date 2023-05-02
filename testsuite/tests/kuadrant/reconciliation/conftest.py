"""Conftest for reconciliation tests"""
import backoff
import pytest


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add anonymous identity"""
    authorization.identity.anonymous("anonymous")
    return authorization


@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization):
    """Only commit authorization"""
    request.addfinalizer(authorization.delete)
    authorization.commit()


@pytest.fixture(scope="module")
def kuadrant(kuadrant):
    """Skip if not running on Kuadrant"""
    if not kuadrant:
        pytest.skip("Reconciliation test can only be run on Kuadrant")
    return kuadrant


@pytest.fixture(scope="module")
def resilient_request(client):
    """Fixture which allows to send retrying requests until the expected status code is returned"""

    def _request(path, method="get", expected_status=200, http_client=client, max_tries=4):
        return backoff.on_predicate(
            backoff.expo, lambda x: x.status_code == expected_status, max_tries=max_tries, jitter=None
        )(lambda: getattr(http_client, method)(path))()

    return _request
