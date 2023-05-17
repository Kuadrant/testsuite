"""Test condition to skip the response section of AuthConfig"""
import pytest

from testsuite.objects import Rule
from testsuite.utils import extract_from_response


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add to the AuthConfig response, which will only trigger on POST requests"""
    authorization.responses.add(
        {
            "name": "auth-json",
            "json": {
                "properties": [
                    {"name": "auth", "value": "response"},
                ]
            },
        },
        when=[Rule("context.request.http.method", "eq", "POST")],
    )
    return authorization


def test_skip_response(client, auth):
    """
    Send GET and POST requests to the same endpoint,
    verify that POST request will return conditional response
    """
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    # verify that response was not returned on a GET request
    with pytest.raises(KeyError, match="Auth-Json"):
        extract_from_response(response)

    response = client.post("/post", auth=auth)
    assert response.status_code == 200
    # verify that response is returned on a POST request
    assert extract_from_response(response)
