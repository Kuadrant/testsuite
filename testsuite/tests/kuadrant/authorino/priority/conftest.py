"""Conftest for Authorino priorities tests"""

import pytest


@pytest.fixture(scope="module")
def authorization(authorization):
    """
    Add to the AuthConfig response with *auth* key from AuthJson,
    to test used identity and resolved metadata dependencies
    """
    authorization.responses.add_simple("auth")
    return authorization
