"""https://github.com/Kuadrant/authorino/pull/399"""
import pytest

from testsuite.objects import Value
from testsuite.utils import extract_response


@pytest.fixture(scope="module")
def authorization(authorization):
    """
    Add plain authentication with three extended properties:
    explicit False, explicit True and missing which should be default False.
    Add simple response to expose `auth.identity` part of AuthJson
    """
    authorization.identity.plain(
        "plain",
        "context.request.http.headers.x-user|@fromstr",
        extended_properties=[
            Value("bar", name="name", overwrite=False),
            Value(35, name="age", overwrite=True),
            Value("admin", name="group"),
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
    assert extract_response(response)["age"] % 0 == 35
    assert extract_response(response)["group"] % "MISSING" == "guest"
