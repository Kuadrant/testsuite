"""https://github.com/Kuadrant/authorino/blob/main/docs/user-guides/token-normalization.md"""
import pytest
from testsuite.policy.authorization import Rule, Value, ValueFrom
from testsuite.httpx.auth import HeaderApiKeyAuth, HttpxOidcClientAuth


@pytest.fixture(scope="module")
def api_key(create_api_key, module_label):
    """Creates API key Secret."""
    return create_api_key("api-key", module_label, "api_key_value")


@pytest.fixture(scope="module")
def auth_api_key(api_key):
    """Return Api key auth"""
    return HeaderApiKeyAuth(api_key)


@pytest.fixture(scope="module")
def auth_oidc_admin(rhsso, blame):
    """Creates new user with new 'admin' role and return auth for it."""
    realm_role = rhsso.realm.create_realm_role("admin")
    user = rhsso.realm.create_user(blame("someuser"), blame("password"))
    user.assign_realm_role(realm_role)
    return HttpxOidcClientAuth.from_user(rhsso.get_token, user, "authorization")


@pytest.fixture(scope="module")
def authorization(authorization, rhsso, api_key):
    """
    Add rhsso identity provider with extended property "roles" which is dynamically mapped to
    list of granted realm roles 'auth.identity.realm_access.roles'
    Add api_key identity with extended property "roles" which is static list of one role 'admin'.

    Add authorization rule allowing DELETE method only to users with role 'admin' in 'auth.identity.roles'
    """
    authorization.identity.add_oidc(
        "rhsso",
        rhsso.well_known["issuer"],
        overrides_properties={"roles": ValueFrom("auth.identity.realm_access.roles")},
    )
    authorization.identity.add_api_key(
        "api_key",
        selector=api_key.selector,
        defaults_properties={"roles": Value(["admin"])},
    )

    rule = Rule(selector="auth.identity.roles", operator="incl", value="admin")
    when = Rule(selector="context.request.http.method", operator="eq", value="DELETE")
    authorization.authorization.add_auth_rules("only-admins-can-delete", rules=[rule], when=[when])
    return authorization


def test_token_normalization(client, auth, auth_oidc_admin, auth_api_key):
    """
    Tests token normalization scenario where three users with different types of authentication have "roles" value
    normalized via extended_properties. Only user with an 'admin' role can use method DELETE.
    - auth: oidc user without 'admin' role
    - auth_oidc_admin: oidc user with 'admin' role
    - auth_api_key: api key user which has static 'admin' role
    """

    assert client.get("/get", auth=auth).status_code == 200
    assert client.delete("/delete", auth=auth).status_code == 403
    assert client.delete("/delete", auth=auth_oidc_admin).status_code == 200
    assert client.delete("/delete", auth=auth_api_key).status_code == 200
