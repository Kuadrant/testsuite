"""Conftest for multicluster tests using a shared database storage."""

import pytest
from dynaconf import ValidationError

from testsuite.kubernetes.secret import Secret


@pytest.fixture(scope="session", params=["redis", "dragonfly", "valkey"])
def storage_service(testconfig, request, skip_or_fail):
    """Returns the multicluster-accessible URL of the storage tool service."""
    try:
        testconfig.validators.validate(only=f"{request.param}.url")
        return testconfig[request.param]["url"]
    except ValidationError as exc:
        return skip_or_fail(f"{request.param} is missing: {exc}")


@pytest.fixture(scope="session")
def storage_secret1(testconfig, cluster, blame, request, storage_service):
    """Creates the Secret for Limitador in the first cluster."""
    system_project = cluster.change_project(testconfig["service_protection"]["system_project"])

    secret = Secret.create_instance(system_project, blame("storage-secret"), {"URL": storage_service})
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret


@pytest.fixture(scope="session")
def storage_secret2(testconfig, cluster2, blame, request, storage_service):
    """Creates the Secret for Limitador in the second cluster."""
    system_project = cluster2.change_project(testconfig["service_protection"]["system_project"])

    secret = Secret.create_instance(system_project, blame("storage-secret-cl2"), {"URL": storage_service})
    request.addfinalizer(secret.delete)
    secret.commit()
    return secret
