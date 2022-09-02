"""
Test raw http authorization interface.
"""


# pylint: disable=unused-argument
def test_authorized_via_http(authorization, client_http_auth, auth):
    """Test raw http authentization with Keycloak."""
    response = client_http_auth.request("GET", "/check", auth=auth)
    assert response.status_code == 200
    assert response.text == ''
    assert response.headers.get('x-ext-auth-other-json', '') == '{"propX":"valueX"}'


# pylint: disable=unused-argument
def test_unauthorized_via_http(authorization, client_http_auth):
    """Test raw http authentization with unauthorized request."""
    response = client_http_auth.request("GET", "/check")
    assert response.status_code == 401
    assert response.text == ''
