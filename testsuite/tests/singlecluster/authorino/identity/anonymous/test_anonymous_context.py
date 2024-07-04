"""Test for anonymous identity context"""

import pytest

from testsuite.utils import extract_response

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization):
    """Setup AuthConfig for test"""
    authorization.identity.add_anonymous("anonymous")
    authorization.responses.add_simple("auth.identity.anonymous")
    return authorization


def test_anonymous_context(client):
    """
    Test:
        - Make request without authentication
        - Assert that response has the right information in context
    """
    response = client.get("/get")
    assert response.status_code == 200
    assert extract_response(response) % None
