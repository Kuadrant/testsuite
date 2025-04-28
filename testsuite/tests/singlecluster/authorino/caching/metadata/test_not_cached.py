"""Tests for metadata without caching feature"""

import pytest

from testsuite.utils import extract_response

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization, module_label, expectation_path):
    """Adds simple Metadata to the AuthConfig"""
    authorization.metadata.add_http(module_label, expectation_path, "GET")
    return authorization


def test_no_caching(client, auth, module_label, mockserver):
    """Tests value is not cached for metadata without caching feature"""
    response1 = client.get("/get", auth=auth)
    assert response1.status_code == 200
    data = extract_response(response1)[module_label]["uuid"] % None
    assert data is not None

    response2 = client.get("/get", auth=auth)
    assert response2.status_code == 200
    cached_data = extract_response(response2)[module_label]["uuid"] % None
    assert cached_data is not None

    assert cached_data != data
    assert len(mockserver.retrieve_requests(module_label)) == 2
