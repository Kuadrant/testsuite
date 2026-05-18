"""
Conftest for dinosaur test
"""

import pytest

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.kuadrant.policy import CelPredicate
from testsuite.oidc.keycloak import Keycloak
from testsuite.utils import ContentType
from testsuite.kuadrant.policy.authorization import Pattern, PatternRef, Value, ValueFrom, DenyResponse


@pytest.fixture(scope="session")
def admin_rhsso(blame, keycloak):
    """Keycloak Admin realm"""

    info = Keycloak(
        keycloak.server_url,
        keycloak.username,
        keycloak.password,
        blame("admin"),
        blame("client"),
        keycloak.test_username,
        keycloak.test_password,
    )

    info.commit()
    yield info

    # Realm cleanup
    info.delete()


@pytest.fixture(scope="module")
def realm_with_attributes(keycloak):
    """
    Ensure the realm allows a custom user attribute.
    """
    keycloak.realm.add_user_attributes("middleName", "Middle Name")
    return keycloak


@pytest.fixture()
def admin_auth(admin_rhsso):
    """Returns Keycloak authentication object for HTTPX"""
    return HttpxOidcClientAuth(admin_rhsso.get_token, "authorization")


@pytest.fixture(scope="module")
def terms_and_conditions(request, mockserver, module_label):
    """Creates Mockserver Expectation that returns whether terms are required and returns its endpoint"""

    def _terms_and_conditions(value):
        return mockserver.create_response_expectation(
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
        return mockserver.create_response_expectation(
            f"{module_label}-cluster", {"client_id": value}, ContentType.APPLICATION_JSON
        )

    request.addfinalizer(lambda: mockserver.clear_expectation(f"{module_label}-cluster"))
    return _cluster_info


@pytest.fixture(scope="module")
def resource_info(request, mockserver, module_label):
    """Creates Mockserver Expectation that returns info about resource and returns its endpoint"""

    def _resource_info(org_id, owner):
        return mockserver.create_response_expectation(
            f"{module_label}-resource",
            {"org_id": org_id, "owner": owner},
            ContentType.APPLICATION_JSON,
        )

    request.addfinalizer(lambda: mockserver.clear_expectation(f"{module_label}-resource"))
    return _resource_info


@pytest.fixture(scope="module")
def authorization(authorization, keycloak, terms_and_conditions, cluster_info, admin_rhsso, resource_info):
    """Creates complex Authorization Config."""
    path_fourth_element = 'request.path.@extract:{"sep":"/","pos":4}'
    authorization.add_patterns(
        {
            "dinosaurs-route": [Pattern(path_fourth_element, "eq", "dinosaurs")],
            "dinosaur-resource-route": [Pattern("request.path", "matches", "/dinosaurs/[^/]+$")],
            "create-dinosaur-route": [
                Pattern("request.path", "matches", "/dinosaurs/?$"),
                Pattern("request.method", "eq", "POST"),
            ],
            "metrics-federate-route": [
                Pattern(path_fourth_element, "eq", "dinosaurs"),
                Pattern("request.path", "matches", "/metrics/federate$"),
            ],
            "service-accounts-route": [Pattern(path_fourth_element, "eq", "service_accounts")],
            "supported-instance-types-route": [Pattern(path_fourth_element, "eq", "instance_types")],
            "agent-clusters-route": [Pattern(path_fourth_element, "eq", "agent-clusters")],
            "admin-route": [Pattern(path_fourth_element, "eq", "admin")],
            "acl-required": [
                Pattern(path_fourth_element, "neq", "agent-clusters"),
                Pattern(path_fourth_element, "neq", "admin"),
            ],
            "user-sso": [Pattern("auth.identity.iss", "eq", keycloak.well_known["issuer"])],
            "admin-sso": [Pattern("auth.identity.iss", "eq", admin_rhsso.well_known["issuer"])],
            "require-org-id": [Pattern("auth.identity.org_id", "neq", "")],
        }
    )
    authorization.add_rule(
        [
            CelPredicate("request.path.matches('^/anything/dinosaurs_mgmt/.+')"),
            CelPredicate("request.path.split('/')[3] == 'v1'"),
        ]
    )

    authorization.identity.clear_all()
    authorization.identity.add_oidc(
        "user-sso",
        keycloak.well_known["issuer"],
        ttl=3600,
        defaults_properties={"org_id": ValueFrom("auth.identity.middle_name")},
    )
    authorization.identity.add_oidc(
        "admin-sso", admin_rhsso.well_known["issuer"], ttl=3600, when=[PatternRef("admin-route")]
    )

    authorization.metadata.add_http(
        "terms-and-conditions", terms_and_conditions("false"), "GET", when=[PatternRef("create-dinosaur-route")]
    )
    authorization.metadata.add_http(
        "cluster-info", cluster_info(keycloak.client_name), "GET", when=[PatternRef("agent-clusters-route")]
    )
    authorization.metadata.add_http(
        "resource-info", resource_info("123", keycloak.client_name), "GET", when=[PatternRef("dinosaur-resource-route")]
    )

    authorization.authorization.add_auth_rules("bearer-token", [Pattern("auth.identity.typ", "eq", "Bearer")])
    authorization.authorization.add_opa_policy(
        "deny-list",
        """list := [
  "denied-test-user1@example.com"
]
denied { list[_] == input.auth.identity.email }
allow { not denied }
""",
        when=[PatternRef("acl-required")],
    )
    authorization.authorization.add_opa_policy(
        "allow-list",
        """list := [
  "123"
]
allow { list[_] == input.auth.identity.org_id }
""",
        when=[PatternRef("acl-required")],
    )
    authorization.authorization.add_auth_rules(
        "terms-and-conditions",
        [Pattern("auth.metadata.terms-and-conditions.terms_required", "eq", "false")],
        when=[PatternRef("create-dinosaur-route")],
    )
    for name in ["dinosaurs", "metrics-federate", "service-accounts", "supported-instance-types"]:
        authorization.authorization.add_auth_rules(
            name, [PatternRef("user-sso"), PatternRef("require-org-id")], when=[PatternRef(f"{name}-route")]
        )

    authorization.authorization.add_auth_rules(
        "agent-clusters", [PatternRef("user-sso")], when=[PatternRef("agent-clusters-route")]
    )
    authorization.authorization.add_opa_policy(
        "cluster-id",
        """allow { input.auth.identity.azp == object.get(input.auth.metadata, "cluster-info", {}).client_id }""",
        when=[PatternRef("agent-clusters-route")],
    )
    authorization.authorization.add_opa_policy(
        "owner",
        """org_id := input.auth.identity.org_id
filter_by_org { org_id }
is_org_admin := input.auth.identity.is_org_admin
resource_data := object.get(input.auth.metadata, "resource-info", {})
same_org { resource_data.org_id == org_id }
is_owner { resource_data.owner == input.auth.identity.azp }
has_permission { filter_by_org; same_org; is_org_admin }
has_permission { filter_by_org; same_org; is_owner }
has_permission { not filter_by_org; is_owner }
method := input.context.request.http.method
allow { method == "GET";    has_permission }
allow { method == "DELETE"; has_permission }
allow { method == "PATCH";  has_permission }
""",
        when=[PatternRef("dinosaur-resource-route")],
    )
    authorization.authorization.add_opa_policy(
        "admin-rbac",
        """method := input.context.request.http.method
roles := input.auth.identity.realm_access.roles
allow { method == "GET";    roles[_] == "admin-full" }
allow { method == "GET";    roles[_] == "admin-read" }
allow { method == "GET";    roles[_] == "admin-write" }
allow { method == "PATCH";  roles[_] == "admin-full" }
allow { method == "PATCH";  roles[_] == "admin-write" }
allow { method == "DELETE"; roles[_] == "admin-full" }
""",
        when=[PatternRef("admin-route"), PatternRef("admin-sso")],
    )
    authorization.authorization.add_opa_policy(
        "require-admin-sso",
        """allow { false }""",
        when=[PatternRef("admin-route"), PatternRef("user-sso")],
    )
    authorization.authorization.add_auth_rules(
        "internal-endpoints", [Pattern(path_fourth_element, "neq", "authz-metadata")]
    )

    authorization.responses.set_unauthorized(
        DenyResponse(
            headers={"content-type": Value("application/json")},
            body=Value(
                """{
  "kind": "Error",
  "id": "403",
  "href": "/api/dinosaurs_mgmt/v1/errors/403",
  "code": "DINOSAURS-MGMT-403",
  "reason": "Forbidden"
}"""
            ),
        )
    )

    return authorization


@pytest.fixture(scope="module")
def user_with_valid_org_id(keycloak, realm_with_attributes, blame):
    """
    Creates new user with valid middle name.
    Middle name is mapped to org ID in auth config.
    """

    keycloak = realm_with_attributes
    user = keycloak.realm.create_user(blame("someuser"), blame("password"), attributes={"middleName": ["123"]})
    return HttpxOidcClientAuth.from_user(keycloak.get_token, user=user)


@pytest.fixture(scope="module", params=["321", None])
def user_with_invalid_org_id(request, realm_with_attributes, keycloak, blame):
    """
    Creates new user with invalid middle name.
    Middle name is mapped to org ID in auth config.
    """
    keycloak = realm_with_attributes
    user = keycloak.realm.create_user(blame("someuser"), blame("password"), attributes={"middleName": request.param})
    return HttpxOidcClientAuth.from_user(keycloak.get_token, user=user)


@pytest.fixture(scope="module")
def user_with_invalid_email(keycloak, realm_with_attributes, blame):
    """Creates new user with invalid email"""
    keycloak = realm_with_attributes
    user = keycloak.realm.create_user(
        blame("someuser"), blame("password"), email="denied-test-user1@example.com", attributes={"middleName": ["123"]}
    )
    return HttpxOidcClientAuth.from_user(keycloak.get_token, user=user)


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
