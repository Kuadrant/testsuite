"""
Tests for Common feature - Caching
https://github.com/Kuadrant/authorino/blob/main/docs/user-guides/caching.md
"""
from time import sleep

from testsuite.tests.kuadrant.authorino.common_feature.caching.metadata.conftest import extract_metadata, count_requests


def test_cached(client, auth, mockserver, module_label):
    """Tests that metadata are cached"""
    response = client.get("/get", auth=auth)

    assert response.status_code == 200
    assert extract_metadata(response, module_label)
    assert count_requests(mockserver, module_label) == 1


def test_cached_single_evaluation(client, auth, mockserver, module_label):
    """
    Tests cache with two subsequent requests:
        - both requests return the same result
        - only single external value evaluation occurs. The second response contains cached (in-memory) value
    """
    response = client.get("/get", auth=auth)
    meta = extract_metadata(response, module_label)
    response = client.get("/get", auth=auth)
    cached_meta = extract_metadata(response, module_label)

    assert meta == cached_meta
    assert count_requests(mockserver, module_label) == 1


def test_cached_ttl(client, auth, mockserver, module_label, cache_ttl):
    """Tests that cached value expires after ttl"""
    response = client.get("/get", auth=auth)
    meta = extract_metadata(response, module_label)
    sleep(cache_ttl)
    response = client.get("/get", auth=auth)
    cached_meta = extract_metadata(response, module_label)

    assert meta != cached_meta
    assert count_requests(mockserver, module_label) == 2
