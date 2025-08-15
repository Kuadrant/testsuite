"""conftest for tests using Redis or RedisCached"""

import pytest
from dynaconf import ValidationError

from testsuite.kubernetes.secret import Secret


@pytest.fixture(scope="package", params=["redis", "dragonfly", "valkey"])
def storage_service(testconfig, request, skip_or_fail):
    """Url of storage tool service in tools"""
    try:
        testconfig.validators.validate(only=f"{request.param}.url")
        return testconfig[request.param]["url"]
    except ValidationError as exc:
        return skip_or_fail(f"{request.param} is missing: {exc}")


@pytest.fixture(scope="package")
def storage_secret(testconfig, cluster, blame, request, storage_service):
    """Secret created in system_project for use by LimitadorCR"""
    system_project = cluster.change_project(testconfig["service_protection"]["system_project"])
    secret = Secret.create_instance(system_project, blame("storage-secret"), {"URL": storage_service})
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret
