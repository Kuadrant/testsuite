"""https://github.com/Kuadrant/authorino/pull/399"""
import pytest

from testsuite.policy.authorization import Value
from testsuite.utils import extract_response


@pytest.fixture(scope="module")
def authorization(authorization):
    """
    Add plain authentication with defaults and overrides properties.
    Add simple response to expose `auth.identity` part of AuthJson
    """
    authorization.identity.add_plain(
        "plain",
        "context.request.http.headers.x-user|@fromstr",
        defaults_properties={
            "name": Value("bar"),
            "group": Value("admin"),
        },
        overrides_properties={
            "age": Value(35),
            "expire": Value("1-12-1999"),
        },
    )
    authorization.responses.add_simple("auth.identity")

    return authorization


def test_overwrite(client):
    """
    Test overriding and defaults capability. Defaults must not override the value in header but Overrides must do so.
    """
    response = client.get("/get", headers={"x-user": '{"name":"foo","age":30}'})
    assert extract_response(response)["name"] % "MISSING" == "foo"
    assert extract_response(response)["age"] % "MISSING" == 35
    assert extract_response(response)["group"] % "MISSING" == "admin"
    assert extract_response(response)["expire"] % "MISSING" == "1-12-1999"
