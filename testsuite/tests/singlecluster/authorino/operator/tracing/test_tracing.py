"""Test tracing"""

import pytest

from testsuite.utils import extract_response

pytestmark = [pytest.mark.observability, pytest.mark.authorino, pytest.mark.standalone_only]


def test_tracing(client, auth, tracing):
    """Send request and check if it's trace is saved into the tracing client"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    request_id = extract_response(response) % None
    assert request_id is not None

    trace = tracing.get_trace(service="authorino", request_id=request_id, tag_name="authorino.request_id")
    assert len(trace) == 1
