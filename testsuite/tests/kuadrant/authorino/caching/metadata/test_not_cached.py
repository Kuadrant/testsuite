"""Tests for metadata without caching feature"""
import pytest

from testsuite.utils import extract_from_response


@pytest.fixture(scope="module")
def authorization(authorization, module_label, expectation_path):
    """Adds simple Metadata to the AuthConfig"""
    authorization.metadata.http_metadata(module_label, expectation_path, "GET")
    return authorization


def test_no_caching(client, auth, module_label, mockserver):
    """Tests value is not cached for metadata without caching feature"""
    response = client.get("/get", auth=auth)
    data = extract_from_response(response, module_label, "uuid")
    response = client.get("/get", auth=auth)

    assert extract_from_response(response, module_label, "uuid") != data
    assert len(mockserver.retrieve_requests(module_label)) == 2
