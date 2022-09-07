"""
Test raw http authorization interface.
"""


# pylint: disable=unused-argument
def test_authorized_via_http(authorization, client, auth):
    """Test raw http authentization with Keycloak."""
    response = client.get("/check", auth=auth)
    assert response.status_code == 200
    assert response.text == ''
    assert response.headers.get('x-ext-auth-other-json', '') == '{"propX":"valueX"}'


# pylint: disable=unused-argument
def test_unauthorized_via_http(authorization, client):
    """Test raw http authentization with unauthorized request."""
    response = client.get("/check")
    assert response.status_code == 401
    assert response.text == ''
