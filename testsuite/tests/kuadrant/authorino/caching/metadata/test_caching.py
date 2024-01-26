"""Tests metadata caching"""

from time import sleep

import pytest

from testsuite.policy.authorization import ValueFrom, Cache
from testsuite.utils import extract_response


@pytest.fixture(scope="module")
def cache_ttl():
    """Returns TTL in seconds for Cached Metadata"""
    return 5


@pytest.fixture(scope="module")
def authorization(authorization, module_label, expectation_path, cache_ttl):
    """Adds Cached Metadata to the AuthConfig"""
    meta_cache = Cache(cache_ttl, ValueFrom("context.request.http.path"))
    authorization.metadata.add_http(module_label, expectation_path, "GET", cache=meta_cache)
    return authorization


def test_cached(client, auth, module_label, mockserver):
    """
    Tests cache with two subsequent requests:
        - both requests return the same result
        - only single external value evaluation occurs. The second response contains cached (in-memory) value
    """
    response = client.get("/get", auth=auth)
    data = extract_response(response)[module_label]["uuid"] % None
    response = client.get("/get", auth=auth)
    cached_data = extract_response(response)[module_label]["uuid"] % None

    assert cached_data is not None
    assert data is not None
    assert data == cached_data
    assert len(mockserver.retrieve_requests(module_label)) == 1


def test_cached_ttl(client, auth, module_label, cache_ttl, mockserver):
    """Tests that cached value expires after ttl"""
    response = client.get("/get", auth=auth)
    data = extract_response(response)[module_label]["uuid"] % None
    sleep(cache_ttl)
    response = client.get("/get", auth=auth)
    cached_data = extract_response(response)[module_label]["uuid"] % None

    assert cached_data is not None
    assert data is not None
    assert data != cached_data
    assert len(mockserver.retrieve_requests(module_label)) == 2
