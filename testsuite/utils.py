"""Utility functions for testsuite"""
import os
import secrets

from testsuite.certificates import Certificate
from testsuite.config import settings


def generate_tail(tail=5):
    """Returns random suffix"""
    return secrets.token_urlsafe(tail).translate(str.maketrans("", "", "-_")).lower()


def randomize(name, tail=5):
    "To avoid conflicts returns modified name with random sufffix"
    return f"{name}-{generate_tail(tail)}"


def _whoami():
    """Returns username"""
    if 'tester' in settings:
        return settings['tester']

    try:
        return os.getlogin()
    # want to catch broad exception and fallback at any circumstance
    # pylint: disable=broad-except
    except Exception:
        return str(os.getuid())


def chain(certificate: Certificate, *authorities: Certificate) -> Certificate:
    """Chains certificates together"""
    entire_chain = [certificate]
    entire_chain.extend(authorities)
    cert_chain = Certificate(certificate="".join(cert.certificate for cert in entire_chain),
                             key=certificate.key)
    return cert_chain
