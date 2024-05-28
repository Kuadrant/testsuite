"""
Tests for UMA (User Managed Access) and complex Open Policy Agent (OPA) Rego policies.
Based on https://github.com/Kuadrant/authorino/blob/main/docs/user-guides/keycloak-authorization-services.md
The difference is that in this test the permissions for "requester" user to access the protected resource
owned by "owner" user is not given dynamically after "requester" user has attempted to access the protected resource,
instead it is created in advance.
For more details on Keycloak Authorization Services and UMA see
https://www.keycloak.org/docs/latest/authorization_services/index.html
"""

import json

import pytest
from keycloak import KeycloakOpenIDConnection, KeycloakUMA

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.policy.authorization import JsonResponse, ValueFrom, Pattern

pytestmark = [pytest.mark.authorino]


# pylint: disable=line-too-long
@pytest.fixture(scope="module")
def rego_policy(keycloak):
    """
    Complex OPA REGO policy that implements the UMA authorization flow.
    See https://www.keycloak.org/docs/latest/authorization_services/index.html#_service_uma_authorization_process
    In short, in the end the RPT (Requesting Party Token, type of JWT with permissions encoded) is obtained.
    If the permissions retrieved from RPT allow you to access the desired protected resource (resource ids must match)
    under the used scope (HTTP GET) this REGO policy authorizes the request.
    """
    return f"""\
pat := http.send({{"url":"{keycloak.well_known["issuer"]}/protocol/openid-connect/token",\
"method": "post","headers":{{"Content-Type":"application/x-www-form-urlencoded"}},\
"raw_body":"grant_type=client_credentials&client_id={keycloak.client_name}&client_secret={keycloak.client.secret}"}})\
.body.access_token

resource_id := http.send({{"url":concat("",["{keycloak.well_known["issuer"]}/authz/protection/\
resource_set?uri=",input.context.request.http.path]),"method":"get", "headers":\
{{"Authorization":concat(" ",["Bearer ",pat])}}}}).body[0]

scope := lower(input.context.request.http.method)
access_token := trim_prefix(input.context.request.http.headers.authorization, "Bearer ")
default rpt = ""
rpt = access_token {{ object.get(input.auth.identity, "authorization", {{}}).permissions }}
else = rpt_str {{

  ticket := http.send({{"url":"{keycloak.well_known["issuer"]}/authz/protection/permission",\
"method":"post","headers":{{"Authorization":concat(" ",["Bearer ",pat]),"Content-Type":"application/json"}},\
"raw_body":concat("",["[{{\\"resource_id\\":\\"",resource_id,"\\",\\"resource_scopes\\":[\\"",scope,"\\"]}}]"\
])}}).body.ticket

  rpt_str := object.get(http.send({{"url":"{keycloak.well_known["issuer"]}/protocol/openid-connect/token",\
"method":"post","headers":{{"Authorization":concat(" ",\
["Bearer ",access_token]),"Content-Type":"application/x-www-form-urlencoded"}},"raw_body":concat("",\
["grant_type=urn:ietf:params:oauth:grant-type:uma-ticket&ticket=",ticket,"&submit_request=true"])}})\
.body, "access_token", "")
}}
allow {{
  permissions := object.get(io.jwt.decode(rpt)[1], "authorization", {{ "permissions": [] }}).permissions
  permissions[i]
  permissions[i].rsid = resource_id
  permissions[i].scopes[_] = scope
}}
"""


@pytest.fixture(scope="module")
def authorization(authorization, rego_policy):
    """
    Adds OPA REGO policy that implements the UMA Authorization flow.
    Also adds RPT to success header if the request was authorized using standard JWT (no permissions encoded in JWT)
    so that the RPT can be used for subsequent requests.

    allValues set to 'true' so that values of all rules declared in the Rego policy - including value in rpt variable -
    are returned after policy evaluation so that the value from rpt variable can be added to the success header.
    """
    authorization.authorization.add_opa_policy("opa", rego_policy, all_values=True)
    authorization.responses.add_success_header(
        "x-keycloak",
        JsonResponse({"rpt": ValueFrom("auth.authorization.opa.rpt")}),
        when=[Pattern("auth.identity.authorization.permissions", "eq", "")],
    )
    return authorization


@pytest.fixture(scope="module")
def resource_owner_auth(keycloak):
    """
    Auth for user who owns the protected resource, a.k.a. "owner" user.
    The "uma_protection" client role is assigned to the user so that they are allowed to create protected resources.
    """
    owner = keycloak.realm.create_user("owner", "owner")
    role = keycloak.realm.admin.get_client_role(client_id=keycloak.client.client_id, role_name="uma_protection")
    keycloak.realm.admin.assign_client_role(user_id=owner.user_id, client_id=keycloak.client.client_id, roles=[role])
    return HttpxOidcClientAuth.from_user(keycloak.get_token(owner.username, owner.password), owner)


@pytest.fixture(scope="module")
def requester_auth(keycloak):
    """Auth for user who requests the access to the protected resource, a.k.a. "requester" user"""
    requester = keycloak.realm.create_user("requester", "requester")
    return HttpxOidcClientAuth.from_user(keycloak.get_token(requester.username, requester.password), requester)


@pytest.fixture(scope="module")
def owner_uma(keycloak, resource_owner_auth):
    """UMA client used to create a protected resource and assign permissions for "requester" to access it."""
    keycloak_connection = KeycloakOpenIDConnection(
        server_url=keycloak.server_url,
        client_id=keycloak.client_name,
        client_secret_key=keycloak.client.secret,
        username=resource_owner_auth.username,
        password=resource_owner_auth.password,
        realm_name=keycloak.realm_name,
    )
    return KeycloakUMA(keycloak_connection)


@pytest.fixture(scope="module")
def protected_resource(owner_uma, resource_owner_auth):
    """
    Protected resource created by and owned by "owner" user
    """
    resource_representation = owner_uma.resource_set_create(
        payload={
            "name": "anything-1",
            "uris": ["/anything/1"],
            "owner": resource_owner_auth.username,
            "ownerManagedAccess": "true",
            "scopes": ["get", "post"],
        }
    )
    return resource_representation


def test_user_managed_access(client, resource_owner_auth, requester_auth, protected_resource, owner_uma):
    """Tests that UMA authorization flow works as expected."""

    # Access the protected resource by requester
    response = client.get("/anything/1", auth=requester_auth)
    assert response.status_code == 403

    # Access the protected resource by the resource owner is forbidden since there are no permissions configured
    # The mere ownership is not sufficient to access it
    response = client.get("/anything/1", auth=resource_owner_auth)
    assert response.status_code == 403

    # Allow HTTP GET access to the protected resource for "requester" user
    # Only resource owner is allowed to do this
    owner_uma.policy_resource_create(
        protected_resource["_id"],
        {
            "name": "Allow GET for requester",
            "description": "Allow GET for requester",
            "scopes": ["get"],
            "users": [requester_auth.username],
        },
    )

    # Owner is allowed to access the protected resource now too - unclear if this is a bug or feature in Keycloak
    response = client.get("/anything/1", auth=resource_owner_auth)
    assert response.status_code == 200

    # Access the protected resource by requester again, should be OK now
    # RPT should be included in the response thanks to success header configured to be added in AuthPolicy CR
    response = client.get("/anything/1", auth=requester_auth)
    assert response.status_code == 200

    # Extract the RPT from the response
    rpt = json.loads(response.json()["headers"]["X-Keycloak"])["rpt"]

    # Access the protected resource by requester using RPT (type of JWT)
    response = client.get("/anything/1", headers={"Authorization": f"Bearer {rpt}"})
    assert response.status_code == 200

    # Access the protected resource by requester using RPT via HTTP POST (scope that is not allowed)
    response = client.post("/anything/1", headers={"Authorization": f"Bearer {rpt}"})
    assert response.status_code == 403


def test_access_non_existent_resource(client, requester_auth):
    """Tests that request for non-existent resource is rejected."""
    response = client.get("/anything/2", auth=requester_auth)
    assert response.status_code == 403
