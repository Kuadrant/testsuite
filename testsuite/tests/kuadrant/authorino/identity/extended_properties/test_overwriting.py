"""https://github.com/Kuadrant/authorino/pull/399"""
import pytest

from testsuite.objects import ExtendedProperty, Value
from testsuite.utils import extract_response


@pytest.fixture(scope="module")
def authorization(authorization):
    """
    Add plain authentication with three extended properties:
    explicit False, explicit True and missing which should be default False.
    Add simple response to expose `auth.identity` part of AuthJson
    """
    authorization.identity.add_plain(
        "plain",
        "context.request.http.headers.x-user|@fromstr",
        extended_properties=[
            ExtendedProperty("name", Value("bar"), overwrite=False),
            ExtendedProperty("age", Value(35), overwrite=True),
            ExtendedProperty("group", Value("admin")),
        ],
    )
    authorization.responses.add_simple("auth.identity")

    return authorization


def test_overwrite(client):
    """
    Test the ExtendedProperty overwrite functionality overwriting the value in headers when True.
    """
    response = client.get("/get", headers={"x-user": '{"name":"foo","age":30,"group":"guest"}'})
    assert extract_response(response)["name"] % "MISSING" == "foo"
    assert extract_response(response)["age"] % "MISSING" == 35
    assert extract_response(response)["group"] % "MISSING" == "guest"
