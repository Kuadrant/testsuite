"""Helper for JWT cookie testing"""

from contextlib import contextmanager


class JWTCookieHelper:
    """Helper for managing JWT cookies in tests"""

    def __init__(self, client):
        self.client = client

    @contextmanager
    def set_jwt_cookie(self, token_value: str):
        """Context manager for setting JWT cookies with automatic cleanup"""
        self.client.cookies.set("jwt", token_value)
        try:
            yield
        finally:
            self.client.cookies.clear()

    def test_with_valid_token(self, token: str, expected_status: int = 200):
        """Test request with valid JWT token"""
        with self.set_jwt_cookie(token):
            response = self.client.get("/")
            assert response.status_code == expected_status
            return response

    def test_with_invalid_token(self, token: str = "invalid", expected_status: int = 302):
        """Test request with invalid JWT token"""
        with self.set_jwt_cookie(token):
            response = self.client.get("/")
            assert response.status_code == expected_status
            return response

    def test_empty_cookie(self, expected_status: int = 302):
        """Test request with empty JWT cookie"""
        return self.test_with_invalid_token("", expected_status)

    def test_malformed_jwt(self, expected_status: int = 302):
        """Test request with malformed JWT"""
        return self.test_with_invalid_token("not.a.jwt", expected_status)

    def test_tampered_signature(self, valid_token: str, expected_status: int = 302):
        """Test request with tampered JWT signature"""
        parts = valid_token.split(".")
        if len(parts) == 3:
            tampered = f"{parts[0]}.{parts[1]}.tampered_signature"
            return self.test_with_invalid_token(tampered, expected_status)
        raise ValueError("Invalid JWT token format")
