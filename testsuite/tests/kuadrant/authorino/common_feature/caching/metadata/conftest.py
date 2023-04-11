"""Conftest for Caching"""
import json

import pytest

from testsuite.objects import Cache, Value


def extract_metadata(response, metadata_name):
    """Extracts the UUID expectation from the request metadata"""
    return json.loads(response.json()["headers"]["Auth-Json"])["auth"].get(metadata_name).get("uuid")


def count_requests(mockserver, expectation_id):
    """Counts the number of requests received by the expectation"""
    return len(mockserver.verify_expectation(f"/{expectation_id}").json())


@pytest.fixture(scope="module")
def cache_ttl():
    """Returns TTL in seconds for Cached Metadata"""
    return 5


@pytest.fixture(autouse=True)
def uuid_expectation(request, mockserver, module_label):
    """Creates Mockserver Expectation which returns random UUID"""
    mustache_template = "{ statusCode: 200, body: { 'uuid': '{{ uuid }}' } };"
    request.addfinalizer(lambda: mockserver.clear_expectation(module_label))
    return mockserver.create_template_expectation(module_label, mustache_template)


@pytest.fixture(scope="module")
def authorization(authorization, mockserver, module_label, cache_ttl):
    """Adds Cached Metadata to the AuthConfig"""
    meta_cache = Cache(cache_ttl, Value(jsonPath="context.request.http.path"))
    authorization.metadata.http_metadata(
        module_label, mockserver.get_expectation_endpoint(module_label), "GET", cache=meta_cache
    )
    authorization.responses.add(
        {"name": "auth-json", "json": {"properties": [{"name": "auth", "valueFrom": {"authJSON": "auth.metadata"}}]}}
    )
    return authorization


@pytest.fixture(autouse=True)
def commit(request, authorization):
    """Commits all important stuff before tests"""
    request.addfinalizer(authorization.delete)
    authorization.commit()
