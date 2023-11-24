"""Test condition to skip the response section of AuthConfig"""
import pytest

from testsuite.policy.authorization import Pattern, Value, JsonResponse
from testsuite.utils import extract_response


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add to the AuthConfig response, which will only trigger on POST requests"""
    authorization.responses.add_success_header(
        "simple", JsonResponse({"data": Value("response")}), when=[Pattern("context.request.http.method", "eq", "POST")]
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
    assert "Simple" not in response.json()["headers"]

    response = client.post("/post", auth=auth)
    assert response.status_code == 200
    # verify that response is returned on a POST request
    value = extract_response(response) % None
    assert value == "response"
