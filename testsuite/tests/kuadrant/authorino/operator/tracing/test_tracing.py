"""Test tracing"""

import pytest

from testsuite.utils import extract_response

pytestmark = [pytest.mark.authorino, pytest.mark.standalone_only]


def test_tracing(client, auth, tracing):
    """Send request and check if it's trace is saved into the tracing client"""
    response = client.get("/get", auth=auth)
    assert response.status_code == 200

    request_id = extract_response(response) % None
    assert request_id is not None

    trace = tracing.find_trace(request_id, "authorino")
    assert len(trace) == 1
