"""Tests metadata caching"""

import pytest

from testsuite.kuadrant.policy.authorization import ValueFrom, Cache
from testsuite.utils import extract_response

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization, module_label, expectation_path):
    """Adds Cached Metadata to the AuthConfig"""
    meta_cache = Cache(5, ValueFrom("context.request.http.path"))
    authorization.metadata.add_http(module_label, expectation_path, "GET", cache=meta_cache)
    return authorization


def test_cached(client, auth, module_label, mockserver):
    """
    Tests cache with two subsequent requests:
        - both requests return the same result
        - only single external value evaluation occurs. The second response contains cached (in-memory) value
    """
    response1 = client.get("/get", auth=auth)
    assert response1.status_code == 200
    data = extract_response(response1)[module_label]["uuid"] % None
    assert data is not None

    response2 = client.get("/get", auth=auth)
    assert response2.status_code == 200
    cached_data = extract_response(response2)[module_label]["uuid"] % None
    assert cached_data is not None

    assert data == cached_data
    assert len(mockserver.retrieve_requests(module_label)) == 1
