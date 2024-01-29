"""Objects for RHSSO"""

from functools import cached_property
from urllib.parse import urlparse

from keycloak import KeycloakOpenID, KeycloakAdmin, KeycloakPostError

from testsuite.oidc import OIDCProvider, Token
from testsuite.lifecycle import LifecycleObject
from .objects import Realm, Client, User


# pylint: disable=too-many-instance-attributes
class RHSSO(OIDCProvider, LifecycleObject):
    """
    OIDCProvider implementation for RHSSO. It creates Realm, client and user.
    """

    def __init__(
        self,
        server_url,
        username,
        password,
        realm_name,
        client_name,
        test_username="testUser",
        test_password="testPassword",
    ) -> None:
        self.test_username = test_username
        self.test_password = test_password
        self.username = username
        self.password = password
        self.realm_name = realm_name
        self.client_name = client_name
        self.realm = None
        self.user = None
        self.client = None

        try:
            self.master = KeycloakAdmin(
                server_url=server_url,
                username=username,
                password=password,
                realm_name="master",
                verify=False,
            )
            self.server_url = server_url
        except KeycloakPostError:
            # Older Keycloaks versions (and RHSSO) needs requires url to be pointed at auth/ endpoint
            # pylint: disable=protected-access
            self.server_url = urlparse(server_url)._replace(path="auth/").geturl()
            self.master = KeycloakAdmin(
                server_url=self.server_url,
                username=username,
                password=password,
                realm_name="master",
                verify=False,
            )

    def create_realm(self, name: str, **kwargs) -> Realm:
        """Creates new realm"""
        self.master.create_realm(payload={"realm": name, "enabled": True, "sslRequired": "None", **kwargs})
        return Realm(self.master, name)

    def commit(self):
        self.realm: Realm = self.create_realm(self.realm_name, accessTokenLifespan=24 * 60 * 60)

        self.client = self.realm.create_client(
            name=self.client_name,
            directAccessGrantsEnabled=True,
            publicClient=False,
            protocol="openid-connect",
            standardFlowEnabled=False,
            serviceAccountsEnabled=True,
            authorizationServicesEnabled=True,
        )
        self.user = self.realm.create_user(self.test_username, self.test_password)

    def delete(self):
        self.realm.delete()

    @property
    def oidc_client(self) -> KeycloakOpenID:
        """OIDCClient for the created client"""
        return self.client.oidc_client  # type: ignore

    @cached_property
    def well_known(self):
        return self.oidc_client.well_known()

    def refresh_token(self, refresh_token):
        """Refreshes token"""
        data = self.oidc_client.refresh_token(refresh_token)
        return Token(data["access_token"], self.refresh_token, data["refresh_token"])

    def get_token(self, username=None, password=None) -> Token:
        data = self.oidc_client.token(username or self.test_username, password or self.test_password)
        return Token(data["access_token"], self.refresh_token, data["refresh_token"])

    def get_public_key(self):
        """Return formatted public key"""
        return "-----BEGIN PUBLIC KEY-----\n" + self.oidc_client.public_key() + "\n-----END PUBLIC KEY-----"

    def token_params(self) -> str:
        """
        Returns token parameters that can be added to request url
        """
        return (
            f"grant_type=password&client_id={self.oidc_client.client_id}&"
            f"client_secret={self.oidc_client.client_secret_key}&username={self.test_username}&"
            f"password={self.test_password}"
        )
