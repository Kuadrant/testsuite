"""Test condition to skip the metadata section of AuthConfig"""
import pytest

from testsuite.policy.authorization import Pattern


@pytest.fixture(scope="module")
def mockserver_expectation(request, mockserver, module_label):
    """Creates Mockserver Expectation which returns non-empty response on hit"""
    request.addfinalizer(lambda: mockserver.clear_expectation(module_label))
    return mockserver.create_expectation(module_label, "response")


@pytest.fixture(scope="module")
def authorization(authorization, mockserver_expectation):
    """
    Add to the AuthConfig metadata evaluator with get http request to the mockserver,
    which will be only triggered on POST requests to the endpoint
    """
    when_post = [Pattern("context.request.http.method", "eq", "POST")]
    authorization.metadata.add_http("mock", mockserver_expectation, "GET", when=when_post)
    return authorization


def test_skip_metadata(client, auth, mockserver, module_label):
    """Send GET and POST requests to the same endpoint, verify that only POST request triggered metadata"""
    # ensure that there are no expectation hits at the beginning
    assert len(mockserver.retrieve_requests(module_label)) == 0

    response = client.get("/get", auth=auth)
    assert response.status_code == 200
    # verify that GET request did not trigger metadata http request to the mockserver
    assert len(mockserver.retrieve_requests(module_label)) == 0

    response = client.post("/post", auth=auth)
    assert response.status_code == 200
    # verify that POST request did trigger metadata http request to the mockserver
    assert len(mockserver.retrieve_requests(module_label)) == 1
