import pytest

from testsuite.kuadrant.extensions.oidc_policy import OIDCPolicy, Provider

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino]

@pytest.mark.parametrize("gateway", ["wildcard_domain", "exact_hostname", "no_hostname"], indirect=True)
@pytest.mark.parametrize("oidc_client", ["public_client", "service_client", "confidential_client"], indirect=True)
def test_oidc_policy(client, auth):
    """Test OIDC policy with both public and confidential clients"""
    response = client.get("/", auth=auth)
    assert response.status_code == 200