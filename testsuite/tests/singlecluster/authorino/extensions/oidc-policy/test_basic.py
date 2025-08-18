import pytest

from testsuite.kuadrant.extensions.oidc_policy import OIDCPolicy, Provider

pytestmark = [pytest.mark.kuadrant_only, pytest.mark.authorino]


@pytest.mark.parametrize(
    "oidc_provider",
    [pytest.param("keycloak", marks=[pytest.mark.smoke])],  # Add more providers as needed
    indirect=True,
)
def test_oidc_policy(client, oidc_policy, auth):
    response = client.get("/", auth=auth)
    assert response.status_code == 200