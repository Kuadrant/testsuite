import pytest

from testsuite.kuadrant.policy.authorization import Pattern

pytestmark = [pytest.mark.authorino]

@pytest.fixture(scope="module", autouse=True)
def client_secret(create_client_secret, keycloak, blame):
    """create the required secrets that will be used by Authorino to authenticate with Keycloak"""
    return create_client_secret(blame("secret"), keycloak.client.auth_id, keycloak.client.secret)

@pytest.fixture(scope="module")
def authorization(client_secret, authorization, keycloak):
    """
    On every request, Authorino will try to verify the token remotely with the Keycloak server with the introspect
    endpoint. It's credentials are referenced from the secret created before.
    """
    authorization.identity.add_item("keycloak", {
        "oauth2Introspection" : {
            "endpoint" : f"{keycloak.server_url}/realms/{keycloak.realm_name}/protocol/openid-connect/token/introspect",
            "tokenTypeHint": "requesting_party_token",
            "credentialsRef" : {
                "name" : client_secret.name()
            }
        }
    })
    return authorization

def test_no_token(client, auth):
    """Test access with no auth"""
    response = client.get("get")
    assert response.status_code == 401

def test_access_token(client, auth):
    """Tests auth with token granted from fixture"""
    response = client.get("get", auth=auth)
    assert response.status_code == 200


def test_revoked_token(client, auth, keycloak):
    """Revoke token by logging out and test if is unauthorized"""
    keycloak.oidc_client.logout(auth.token.refresh_token)
    response = client.get("get", auth=auth)
    assert response.status_code == 401