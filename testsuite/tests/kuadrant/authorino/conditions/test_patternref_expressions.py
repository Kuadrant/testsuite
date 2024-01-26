"""Test patterns reference functionality and All/Any logical expressions."""

import pytest

from testsuite.policy.authorization import Pattern, PatternRef, AnyPattern, AllPattern


@pytest.fixture(scope="module")
def authorization(authorization):
    """
    Add multiple named patterns to AuthConfig to be referenced in later authorization rules.
    Create authorization rule which:
    1. For a GET requests allows only paths "/anything/dog" and "/anything/cat"
    2. For a POST requests allows only paths "/anything/apple" and "/anything/pear"
    3. For requests that contain header "x-special" it will get authorized regardless.
    """
    authorization.add_patterns(
        {
            "apple": [Pattern("context.request.http.path", "eq", "/anything/apple")],
            "pear": [Pattern("context.request.http.path", "eq", "/anything/pear")],
            "dog": [Pattern("context.request.http.path", "eq", "/anything/dog")],
            "cat": [Pattern("context.request.http.path", "eq", "/anything/cat")],
            "get": [Pattern("context.request.http.method", "eq", "GET")],
            "post": [Pattern("context.request.http.method", "eq", "POST")],
        }
    )

    authorization.authorization.add_auth_rules(
        "auth_rules",
        [
            AnyPattern(
                [
                    AllPattern([AnyPattern([PatternRef("dog"), PatternRef("cat")]), PatternRef("get")]),
                    AllPattern([AnyPattern([PatternRef("apple"), PatternRef("pear")]), PatternRef("post")]),
                    Pattern("context.request.http.headers.@keys", "incl", "x-special"),
                ]
            )
        ],
    )

    return authorization


@pytest.mark.parametrize(
    "path, expected_code",
    [
        ("/get", 403),
        ("/anything/rock", 403),
        ("/anything/apple", 403),
        ("/anything/pear", 403),
        ("/anything/dog", 200),
        ("/anything/cat", 200),
    ],
)
def test_get_rule(client, auth, path, expected_code):
    """Test if doing GET request adheres to specified auth rule."""
    assert client.get(path, auth=auth).status_code == expected_code


@pytest.mark.parametrize(
    "path, expected_code",
    [
        ("/post", 403),
        ("/anything/rock", 403),
        ("/anything/apple", 200),
        ("/anything/pear", 200),
        ("/anything/dog", 403),
        ("/anything/cat", 403),
    ],
)
def test_post_rule(client, auth, path, expected_code):
    """Test if doing POST request adheres to specified auth rule."""
    assert client.post(path, auth=auth).status_code == expected_code


def test_special_header_rule(client, auth):
    """Test if using the "x-special" header adheres to specified auth rule."""
    assert client.get("/get", auth=auth, headers={"x-special": "value"}).status_code == 200
    assert client.post("/post", auth=auth, headers={"x-special": "value"}).status_code == 200
