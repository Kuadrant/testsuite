"""Test for custom deny responses."""

from json import loads
import pytest

from testsuite.policy.authorization import Pattern, Value, ValueFrom, DenyResponse

HEADERS = {
    "x-string-header": Value("abc"),
    "x-int-header": Value(16),
    "x-list-header": Value([1, 2, 3]),
    "x-dict-header": Value({"anything": "something"}),
    "x-dynamic-header": ValueFrom("context.request.http.path"),
}

TESTING_PATH = "/deny"


@pytest.fixture(scope="module")
def authorization(authorization):
    """Set custom deny responses and auth rule with only allowed path '/allow'"""
    authorization.responses.set_unauthenticated(
        DenyResponse(
            code=333,
            headers=HEADERS,
            message=Value("Unauthenticated message"),
            body=Value("You are unauthenticated."),
        )
    )
    authorization.responses.set_unauthorized(
        DenyResponse(
            code=444,
            headers=HEADERS,
            message=ValueFrom("My path is: " + "{context.request.http.path}"),
            body=ValueFrom("You are not authorized to access path: " + "{context.request.http.path}"),
        )
    )
    # Authorize only when url path is "/allow"
    authorization.authorization.add_auth_rules("Whitelist", [Pattern("context.request.http.path", "eq", "/allow")])
    return authorization


def assert_headers(response):
    """Check deny headers with normalization between HTTP (JSON) strings and Python objects."""
    assert response.headers["x-string-header"] == HEADERS["x-string-header"].value
    assert loads(response.headers["x-int-header"]) == HEADERS["x-int-header"].value
    assert loads(response.headers["x-list-header"]) == HEADERS["x-list-header"].value
    assert loads(response.headers["x-dict-header"]) == HEADERS["x-dict-header"].value
    assert response.headers["x-dynamic-header"] == TESTING_PATH


def test_unauthenticated(client):
    """Test when no auth is passed results in custom unauthenticated response."""
    response = client.get(TESTING_PATH, auth=None)
    assert response.status_code == 333
    assert_headers(response)
    assert response.headers["x-ext-auth-reason"] == "Unauthenticated message"
    assert response.content.decode() == "You are unauthenticated."


def test_unauthorized(client, auth):
    """Test when not allowed path is passed results in custom unauthorized response."""
    response = client.get(TESTING_PATH, auth=auth)
    assert response.status_code == 444
    assert_headers(response)
    assert response.headers["x-ext-auth-reason"] == f"My path is: {TESTING_PATH}"
    assert response.content.decode() == f"You are not authorized to access path: {TESTING_PATH}"
