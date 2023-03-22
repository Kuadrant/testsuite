"""Test api authentication with wristband-token that was acquired after authentication on the edge layer"""
from jose import jwt


def test_wristband_token_claims(oidc_provider, auth, wristband_token, wristband_endpoint, certificates):
    """Verify acquired jwt token claims"""
    wristband_decoded = jwt.decode(wristband_token, certificates["signing_ca"].certificate)
    assert wristband_decoded["exp"] - wristband_decoded["iat"] == 300
    assert wristband_decoded["iss"] == wristband_endpoint
    # check differences in claims between rhsso token and acquired wristband token
    access_token_decoded = jwt.decode(auth.token.access_token, oidc_provider.get_public_key(), audience="account")
    for claim in ["preferred_username", "email", "realm_access", "resource_access"]:
        assert claim in access_token_decoded
        assert claim not in wristband_decoded


def test_wristband_success(client_authenticated, wristband_token):
    """Test api authentication with token that was acquired after successful authentication in the edge"""
    client_authenticated.headers = {"Authorization": "Bearer " + wristband_token}
    response = client_authenticated.get("/get")
    assert response.status_code == 200


def test_wristband_fail(client_authenticated, auth):
    """Test api authentication with token that only accepted in the edge"""
    response = client_authenticated.get("/get", auth=auth)  # oidc access token instead of wristband
    assert response.status_code == 401
