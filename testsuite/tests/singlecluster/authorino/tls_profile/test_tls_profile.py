"""Tests that TLS security profiles are propagated from APIServer CR to Authorino endpoints"""

import ssl
import socket

import pytest

pytestmark = [pytest.mark.authorino, pytest.mark.kuadrant_only, pytest.mark.disruptive]


@pytest.fixture(scope="module")
def probe_tls():
    """
    Returns a callable that probes a TLS endpoint with a specific TLS version,
    and returns the negotiated TLS version and cipher.
    https://docs.python.org/3/library/ssl.html#socket-creation
    """

    def _probe(hostname, max_version=None):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        if max_version is not None:
            context.minimum_version = max_version
            context.maximum_version = max_version
        try:
            with socket.create_connection((hostname, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    return ssock.version(), ssock.cipher()[0]
        except ssl.SSLError:
            return None, None

    return _probe


@pytest.mark.parametrize(
    "tls_profile, accept_version, reject_version, expected_cipher",
    [
        pytest.param(("Modern", "1.3", None), ssl.TLSVersion.TLSv1_3, ssl.TLSVersion.TLSv1_2, None, id="modern"),
        pytest.param(
            ("Intermediate", "1.2", None), ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_1, None, id="intermediate"
        ),
        pytest.param(
            ("Custom", "1.2", ["ECDHE-RSA-AES128-GCM-SHA256"]),
            ssl.TLSVersion.TLSv1_2,
            ssl.TLSVersion.TLSv1_1,
            "ECDHE-RSA-AES128-GCM-SHA256",
            id="custom",
        ),
    ],
    indirect=["tls_profile"],
)
def test_tls_profile(
    tls_profile, accept_version, reject_version, expected_cipher, probe_tls, oidc_route, authorization_route
):  # pylint: disable=unused-argument
    """OIDC and authorization endpoints accept the profile's TLS version and reject lower versions"""
    for hostname in [oidc_route.hostname, authorization_route.hostname]:
        version, cipher = probe_tls(hostname, max_version=accept_version)
        expected_ver = accept_version.name.replace("_", ".")
        assert version == expected_ver, f"Expected TLS version {expected_ver}, got {version}"
        if expected_cipher is not None:
            assert cipher == expected_cipher, f"Expected cipher {expected_cipher}, got {cipher}"
        if reject_version is not None:
            rejected_ver = reject_version.name.replace("_", ".")
            assert probe_tls(hostname, max_version=reject_version)[0] is None, f"TLS {rejected_ver} should be rejected"
