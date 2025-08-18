import pytest

from testsuite.kuadrant.extensions.oidc_policy import OIDCPolicy, Provider

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino]

@pytest.mark.parametrize(
    "oidc_client",
    [
        # Test with public client (Authorization Code + PKCE)
        pytest.param(
            "public_client",
            marks=[pytest.mark.smoke],
            id="public-client"
        ),
        # Test with confidential client (Authorization Code + client secret)
        pytest.param(
            "confidential_client",
            id="confidential-client"
        ),
        # Test with service account client (Client Credentials Grant)
        pytest.param(
            "service_client",
            id="service-client"
        ),
    ],
    indirect=True,
)
def test_oidc_policy(client, oidc_policy, auth):
    """Test OIDC policy with both public and confidential clients"""
    response = client.get("/", auth=auth)
    assert response.status_code == 200