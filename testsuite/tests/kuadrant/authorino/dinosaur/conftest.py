"""
Conftest for anonymized use cases tests
"""
from importlib import resources

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.oidc.rhsso import RHSSO
from testsuite.utils import ContentType


@pytest.fixture(scope="module")
def run_on_kuadrant():
    """We did not implement all the features of this AuthConfig in AuthPolicy"""
    return False


@pytest.fixture(scope="session")
def admin_rhsso(request, testconfig, blame, rhsso):
    """RHSSO OIDC Provider fixture"""

    info = RHSSO(rhsso.server_url, rhsso.username, rhsso.password, blame("realm"), blame("client"),
                 rhsso.test_username, rhsso.test_password)

    if not testconfig["skip_cleanup"]:
        request.addfinalizer(info.delete)
    info.commit()
    return info


@pytest.fixture()
def admin_auth(admin_rhsso):
    """Returns RHSSO authentication object for HTTPX"""
    return HttpxOidcClientAuth(admin_rhsso.get_token, "authorization")


@pytest.fixture(scope="module")
def terms_and_conditions(request, mockserver, module_label):
    """Creates Mockserver Expectation that returns whether terms are required and returns its endpoint"""

    def _terms_and_conditions(value):
        return mockserver.create_expectation(
            f"{module_label}-terms",
            {"terms_required": value},
            ContentType.APPLICATION_JSON,
        )

    request.addfinalizer(lambda: mockserver.clear_expectation(f"{module_label}-terms"))
    return _terms_and_conditions


@pytest.fixture(scope="module")
def cluster_info(request, mockserver, module_label):
    """Creates Mockserver Expectation that returns client ID and returns its endpoint"""

    def _cluster_info(value):
        return mockserver.create_expectation(
            f"{module_label}-cluster",
            {"client_id": value},
            ContentType.APPLICATION_JSON
        )

    request.addfinalizer(lambda: mockserver.clear_expectation(f"{module_label}-cluster"))
    return _cluster_info


@pytest.fixture(scope="module")
def resource_info(request, mockserver, module_label):
    """Creates Mockserver Expectation that returns info about resource and returns its endpoint"""

    def _resource_info(org_id, owner):
        return mockserver.create_expectation(
            f"{module_label}-resource",
            {"org_id": org_id, "owner": owner},
            ContentType.APPLICATION_JSON,
        )

    request.addfinalizer(lambda: mockserver.clear_expectation(f"{module_label}-resource"))
    return _resource_info


@pytest.fixture()
def commit():
    """Ensure no default resources are created"""


@pytest.fixture(scope="module")
def authorization(openshift, blame, envoy, module_label, rhsso, terms_and_conditions, cluster_info, admin_rhsso,
                  resource_info, request):
    """Creates AuthConfig object from template"""
    with resources.path("testsuite.resources", "dinosaur_config.yaml") as path:
        auth = openshift.new_app(path, {
            "NAME": blame("ac"),
            "NAMESPACE": openshift.project,
            "LABEL": module_label,
            "HOST": envoy.hostname,
            "RHSSO_ISSUER": rhsso.well_known['issuer'],
            "ADMIN_ISSUER": admin_rhsso.well_known["issuer"],
            "TERMS_AND_CONDITIONS": terms_and_conditions("false"),
            "CLUSTER_INFO": cluster_info(rhsso.client_name),
            "RESOURCE_INFO": resource_info("123", rhsso.client_name)
        })

        def _delete():
            auth.delete()

        request.addfinalizer(_delete)
        return auth


@pytest.fixture(scope="module")
def user_with_valid_org_id(rhsso, blame):
    """
    Creates new user with valid middle name.
    Middle name is mapped to org ID in auth config.
    """
    user = rhsso.realm.create_user(blame("someuser"), blame("password"))
    user.assign_attribute({"middleName": "123"})
    return HttpxOidcClientAuth.from_user(rhsso.get_token, user=user)


@pytest.fixture(scope="module", params=["321", None])
def user_with_invalid_org_id(rhsso, blame, request):
    """
    Creates new user with valid middle name.
    Middle name is mapped to org ID in auth config.
    """
    user = rhsso.realm.create_user(blame("someuser"), blame("password"))
    user.assign_attribute({"middleName": request.param})
    return HttpxOidcClientAuth.from_user(rhsso.get_token, user=user)


@pytest.fixture(scope="module")
def user_with_invalid_email(rhsso, blame):
    """Creates new user with invalid email"""
    user = rhsso.realm.create_user(blame("someuser"), blame("password"), email="denied-test-user1@example.com")
    user.assign_attribute({"middleName": "123"})
    return HttpxOidcClientAuth.from_user(rhsso.get_token, user=user)


@pytest.fixture(scope="module")
def user_with_full_role(admin_rhsso, blame):
    """Creates new user and adds him into realm_role"""
    user = admin_rhsso.realm.create_user(blame("someuser"), blame("password"))
    user.assign_realm_role(admin_rhsso.realm.create_realm_role("admin-full"))
    return HttpxOidcClientAuth.from_user(admin_rhsso.get_token, user=user)


@pytest.fixture(scope="module")
def user_with_read_role(admin_rhsso, blame):
    """Creates new user and adds him into realm_role"""
    user = admin_rhsso.realm.create_user(blame("someuser"), blame("password"))
    user.assign_realm_role(admin_rhsso.realm.create_realm_role("admin-read"))
    return HttpxOidcClientAuth.from_user(admin_rhsso.get_token, user=user)


@pytest.fixture(scope="module")
def user_with_write_role(admin_rhsso, blame):
    """Creates new user and adds him into realm_role"""
    user = admin_rhsso.realm.create_user(blame("someuser"), blame("password"))
    user.assign_realm_role(admin_rhsso.realm.create_realm_role("admin-write"))
    return HttpxOidcClientAuth.from_user(admin_rhsso.get_token, user=user)
