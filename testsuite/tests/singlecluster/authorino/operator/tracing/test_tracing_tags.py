"""Test custom tags set for request traces"""

import pytest

from testsuite.utils import extract_response

pytestmark = [pytest.mark.observability, pytest.mark.authorino, pytest.mark.standalone_only]


TAG_KEY = "test-key"
TAG_VALUE = "test-value"


@pytest.fixture(scope="module")
def authorino_parameters(authorino_parameters):
    """Deploy authorino with tracing enabled and custom tags set"""
    authorino_parameters["tracing"].tags = {TAG_KEY: TAG_VALUE}
    return authorino_parameters


def test_tracing_tags(client, auth, tracing):
    """Send request and check if it's trace with custom tags is saved into the tracing client"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    request_id = extract_response(response) % None
    assert request_id is not None

    trace = tracing.search(request_id, "authorino", {TAG_KEY: TAG_VALUE})
    assert len(trace) == 1
