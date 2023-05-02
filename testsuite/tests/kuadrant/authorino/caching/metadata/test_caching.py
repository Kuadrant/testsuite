"""Tests metadata caching"""
from time import sleep

import pytest

from testsuite.objects import Cache, Value
from testsuite.utils import extract_from_response


@pytest.fixture(scope="module")
def cache_ttl():
    """Returns TTL in seconds for Cached Metadata"""
    return 5


@pytest.fixture(scope="module")
def authorization(authorization, module_label, expectation_path, cache_ttl):
    """Adds Cached Metadata to the AuthConfig"""
    meta_cache = Cache(cache_ttl, Value(jsonPath="context.request.http.path"))
    authorization.metadata.http_metadata(module_label, expectation_path, "GET", cache=meta_cache)
    return authorization


def test_cached(client, auth, module_label, mockserver):
    """
    Tests cache with two subsequent requests:
        - both requests return the same result
        - only single external value evaluation occurs. The second response contains cached (in-memory) value
    """
    response = client.get("/get", auth=auth)
    data = extract_from_response(response, module_label, "uuid")
    response = client.get("/get", auth=auth)
    cached_data = extract_from_response(response, module_label, "uuid")

    assert data == cached_data
    assert len(mockserver.retrieve_requests(module_label)) == 1


def test_cached_ttl(client, auth, module_label, cache_ttl, mockserver):
    """Tests that cached value expires after ttl"""
    response = client.get("/get", auth=auth)
    data = extract_from_response(response, module_label, "uuid")
    sleep(cache_ttl)
    response = client.get("/get", auth=auth)
    cached_data = extract_from_response(response, module_label, "uuid")

    assert data != cached_data
    assert len(mockserver.retrieve_requests(module_label)) == 2
