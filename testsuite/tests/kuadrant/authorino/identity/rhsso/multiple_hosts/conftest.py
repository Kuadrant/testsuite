"""Conftest for multiple hosts tests"""
import pytest


@pytest.fixture(scope="module")
def hostname(envoy):
    """Original hostname"""
    return envoy.hostname


@pytest.fixture(scope="module")
def second_hostname(envoy, blame):
    """Second valid hostname"""
    return envoy.create_route(blame('second')).model.spec.host
