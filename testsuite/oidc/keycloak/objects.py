"""Object wrappers for Keycloak resources"""

from functools import cached_property
from typing import List

from keycloak import KeycloakOpenID, KeycloakAdmin


class Realm:
    """Helper class for Keycloak realm manipulation"""

    def __init__(self, master: KeycloakAdmin, name) -> None:
        self.admin = KeycloakAdmin(
            server_url=master.connection.server_url,
            username=master.connection.username,
            password=master.connection.password,
            realm_name=name,
            user_realm_name="master",
            verify=False,
        )
        self.name = name

    def delete(self):
        """Deletes realm"""
        self.admin.delete_realm(self.name)

    def create_client(self, name, **kwargs):
        """Creates new client"""
        self.admin.create_client(payload={**kwargs, "clientId": name})
        client_id = self.admin.get_client_id(name)
        return Client(self, client_id)

    def delete_client(self, client_id):
        """Deletes client"""
        self.admin.delete_client(client_id)

    def create_user(self, username, password, **kwargs):
        """Creates new user"""
        kwargs["username"] = username
        kwargs["enabled"] = True
        kwargs.setdefault("firstName", "John")
        kwargs.setdefault("lastName", "Doe")
        kwargs.setdefault("email", f"{username}@anything.invalid")
        self.admin.create_user(kwargs)
        user_id = self.admin.get_user_id(username)
        self.admin.set_user_password(user_id, password, temporary=False)
        self.admin.update_user(user_id, {"emailVerified": True})
        return User(self, user_id, username, password)

    def create_realm_role(self, role_name: str):
        """Creates realm role
        :param role_name: name of role
        :return: Dictionary with two keys "name", "id"
        """
        self.admin.create_realm_role(payload={"name": role_name})
        role_id = self.admin.get_realm_role(role_name)["id"]
        return {"name": role_name, "id": role_id}

    def oidc_client(self, client_id, client_secret):
        """Create OIDC client for this realm"""
        return KeycloakOpenID(
            server_url=self.admin.connection.server_url,
            client_id=client_id,
            realm_name=self.name,
            client_secret_key=client_secret,
        )

    def add_user_attributes(self, attribute_name, display_name):
        """Adds a new custom attribute to the realm's user profile configuration."""
        user_profile = self.admin.get_realm_users_profile()

        new_attribute = {
            "name": attribute_name,
            "displayName": display_name,
            "validations": {},
            "annotations": {},
            "permissions": {"view": ["admin"], "edit": ["admin"]},
            "multivalued": False,
        }

        user_profile["attributes"].append(new_attribute)
        return self.admin.update_realm_users_profile(user_profile)


class Client:
    """Helper class for Keycloak client manipulation"""

    def __init__(self, realm: Realm, client_id) -> None:
        self.admin = realm.admin
        self.realm = realm
        self.client_id = client_id

    def assign_role(self, role_name):
        """Assign client role from realm management client"""
        user = self.admin.get_client_service_account_user(self.client_id)
        realm_management = self.admin.get_client_id("realm-management")
        role = self.admin.get_client_role(realm_management, role_name)
        self.admin.assign_client_role(user["id"], realm_management, role)

    @cached_property
    def auth_id(self):
        """Note This is different clientId (clientId) than self.client_id (Id), because Keycloak"""
        return self.admin.get_client(self.client_id)["clientId"]

    @property
    def secret(self):
        """Client Secret"""
        return self.admin.get_client_secrets(self.client_id)["value"]

    @cached_property
    def oidc_client(self):
        """OIDC client"""
        return self.realm.oidc_client(self.auth_id, self.secret)

    def create_uma_resource(self, name, uris: List[str], owner=None):
        """
        Creates client resource. By default, this resource is not enforcing UMA policy.
        When owner is specified, this policy is enforced and access to this resource is allowed only for the owner.
        """
        resource = {"name": name, "uris": uris}
        if owner:
            resource["owner"] = owner
            resource["ownerManagedAccess"] = True
        return self.admin.create_client_authz_resource(self.client_id, resource)

    def add_user_attribute_mapper(
        self, attribute_name, token_claim_name, add_to_access_token=True, add_to_id_token=True
    ):
        """Adds a user attribute mapper that includes custom user attributes in JWT tokens"""
        mapper_config = {
            "name": f"{attribute_name}-mapper",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-usermodel-attribute-mapper",
            "config": {
                "user.attribute": attribute_name,
                "claim.name": token_claim_name,
                "jsonType.label": "String",
                "id.token.claim": add_to_id_token,
                "access.token.claim": add_to_access_token,
                "userinfo.token.claim": "true",
            },
        }
        return self.admin.add_mapper_to_client(self.client_id, mapper_config)


class User:
    """Wrapper object for User object in Keycloak"""

    def __init__(self, realm: Realm, user_id, username, password) -> None:
        super().__init__()
        self.admin = realm.admin
        self.realm = realm
        self.user_id = user_id
        self.username = username
        self.password = password

    def update_user(self, **properties):
        """Updates user"""
        self.admin.update_user(self.user_id, properties)

    def assign_realm_role(self, role):
        """Assigns realm role to user
        :param role: Dictionary with two keys "name" and "id" of role to assign
        :returns: Keycloak server response
        """
        return self.admin.assign_realm_roles(user_id=self.user_id, roles=role)

    def assign_attribute(self, attribute):
        """Assigns attribute to user"""
        self.update_user(attributes=attribute)

    @property
    def properties(self):
        """Returns User information in a dict"""
        return self.admin.get_user(self.user_id)
