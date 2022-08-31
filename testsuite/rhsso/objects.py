"""Object wrappers of RHSSO resources"""
from urllib.parse import urlparse

from keycloak import KeycloakOpenID, KeycloakAdmin, KeycloakPostError


class Realm:
    """Helper class for RHSSO realm manipulation"""
    def __init__(self, master: KeycloakAdmin, name) -> None:
        self.admin = KeycloakAdmin(server_url=master.server_url,
                                   username=master.username,
                                   password=master.password,
                                   realm_name=name,
                                   user_realm_name="master",
                                   verify=False,
                                   auto_refresh_token=['get', 'put', 'post', 'delete'])
        self.name = name

    def delete(self):
        """Deletes realm"""
        self.admin.delete_realm(self.name)

    def create_client(self, name, **kwargs):
        """Creates new client"""
        self.admin.create_client(payload={
            **kwargs,
            "clientId": name}
        )
        client_id = self.admin.get_client_id(name)
        return Client(self, client_id)

    def create_user(self, username, password, **kwargs):
        """Creates new user"""
        kwargs["username"] = username
        kwargs["enabled"] = True
        kwargs["email"] = f"{username}@anything.invalid"
        self.admin.create_user(kwargs)
        user_id = self.admin.get_user_id(username)
        self.admin.set_user_password(user_id, password, temporary=False)
        self.admin.update_user(user_id, {"emailVerified": True})
        return user_id

    def create_realm_role(self, role_name: str):
        """Creates realm role
        :param role_name: name of role
        :return: Dictionary with two keys "name", "id"
        """
        self.admin.create_realm_role(payload={"name": role_name})
        role_id = self.admin.get_realm_role(role_name)["id"]
        return {"name": role_name, "id": role_id}

    def assign_realm_role(self, role, user_id: str):
        """Assigns realm role to user
        :param role: Dictionary with two keys "name" and "id" of role to assign
        :param user_id: Id of user to assign role to
        :returns: Keycloak server response
        """
        return self.admin.assign_realm_roles(user_id=user_id,
                                             roles=role)

    def oidc_client(self, client_id, client_secret):
        """Create OIDC client for this realm"""
        return KeycloakOpenID(server_url=self.admin.server_url,
                              client_id=client_id,
                              realm_name=self.name,
                              client_secret_key=client_secret)


class Client:
    """Helper class for RHSSO client manipulation"""
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

    @property
    def oidc_client(self):
        """OIDC client"""
        # Note This is different clientId (clientId) than self.client_id (Id), because RHSSO
        client_id = self.admin.get_client(self.client_id)["clientId"]
        secret = self.admin.get_client_secrets(self.client_id)["value"]
        return self.realm.oidc_client(client_id, secret)


class RHSSO:
    """Helper class for RHSSO server"""

    def __init__(self, server_url, username, password) -> None:
        try:
            self.master = KeycloakAdmin(server_url=server_url,
                                        username=username,
                                        password=password,
                                        realm_name="master",
                                        verify=False,
                                        auto_refresh_token=['get', 'put', 'post', 'delete'])
            self.server_url = server_url
        except KeycloakPostError:
            # Older Keycloaks versions (and RHSSO) needs requires url to be pointed at auth/ endpoint
            # pylint: disable=protected-access
            self.server_url = urlparse(server_url)._replace(path="auth/").geturl()
            self.master = KeycloakAdmin(server_url=self.server_url,
                                        username=username,
                                        password=password,
                                        realm_name="master",
                                        verify=False,
                                        auto_refresh_token=['get', 'put', 'post', 'delete'])

    def create_realm(self, name: str, **kwargs) -> Realm:
        """Creates new realm"""
        self.master.create_realm(payload={
            "realm": name,
            "enabled": True,
            "sslRequired": "None",
            **kwargs
        })
        return Realm(self.master, name)

    def create_oidc_client(self, realm, client_id, secret) -> KeycloakOpenID:
        """Creates OIDC client"""
        return KeycloakOpenID(server_url=self.master.server_url,
                              client_id=client_id,
                              realm_name=realm,
                              client_secret_key=secret)
