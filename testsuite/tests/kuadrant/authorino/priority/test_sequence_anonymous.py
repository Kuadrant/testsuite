"""
Test for anonymous identity low priority trigger.
Anonymous identity should trigger after the oidc identity evaluation
"""
import pytest

from testsuite.utils import extract_response


@pytest.fixture(scope="module")
def authorization(authorization):
    """Add anonymous identity with low priority to the AuthConfig"""
    authorization.identity.add_anonymous("anonymous", priority=1)
    return authorization


def test_priority_anonymous(client, auth, oidc_provider):
    """
    Send request with and without oidc authentication.
    Oidc identity, if used, should trigger before the anonymous identity evaluation
    """
    response = client.get("/get", auth=auth)
    assert response.status_code == 200
    iss = extract_response(response)["identity"]["iss"] % None
    assert iss == oidc_provider.well_known["issuer"]

    response = client.get("/get")
    assert response.status_code == 200
    identity = extract_response(response)["identity"] % None
    assert identity == {"anonymous": True}
