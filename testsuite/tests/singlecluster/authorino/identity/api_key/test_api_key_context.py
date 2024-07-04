"""Test for API key identity context"""

import pytest

from testsuite.utils import extract_response

pytestmark = [pytest.mark.authorino]


@pytest.fixture(scope="module")
def authorization(authorization, api_key):
    """Setup AuthConfig for test"""
    authorization.identity.add_api_key("api_key", selector=api_key.selector)
    authorization.responses.add_simple("auth.identity")
    return authorization


def tests_api_key_context(client, auth, api_key, module_label, cluster):
    """
    Test:
        - Make request with API key authentication
        - Assert that response has the right information in context
    """
    response = client.get("get", auth=auth)
    assert response.status_code == 200
    identity = extract_response(response)
    assert identity["data"]["api_key"] % None == api_key.model.data.api_key
    assert identity["metadata"]["namespace"] % None == cluster.project
    assert identity["metadata"]["labels"]["group"] % None == module_label
