"""Utility functions for testsuite"""
import os
import secrets

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
