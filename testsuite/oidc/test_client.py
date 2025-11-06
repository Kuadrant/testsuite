"""OIDC test client wrapper for easier testing"""

from dataclasses import dataclass, field
from typing import Literal
from keycloak import KeycloakOpenID

from testsuite.httpx.auth import HttpxOidcClientAuth
from testsuite.oidc import Token
from testsuite.kuadrant.extensions.oidc_policy import Provider


@dataclass
class ClientConfig:  # pylint: disable=too-many-instance-attributes
    """Configuration for creating OIDC test clients"""

    client_id: str
    client_type: Literal["confidential", "public", "service"]
    redirect_uris: list[str]
    web_origins: list[str]
    root_url: str
    public_client: bool = False
    standard_flow_enabled: bool = True
    service_accounts_enabled: bool = False
    direct_access_grants_enabled: bool = True
    default_client_scopes: list[str] = field(default_factory=lambda: ["openid", "profile", "email"])
    optional_client_scopes: list[str] = field(default_factory=lambda: ["offline_access", "microprofile-jwt"])

    def to_keycloak_payload(self):
        """Convert to Keycloak client creation payload"""
        return {
            "name": self.client_id,
            "clientId": self.client_id,
            "publicClient": self.public_client,
            "standardFlowEnabled": self.standard_flow_enabled,
            "serviceAccountsEnabled": self.service_accounts_enabled,
            "protocol": "openid-connect",
            "redirectUris": self.redirect_uris,
            "webOrigins": self.web_origins,
            "directAccessGrantsEnabled": self.direct_access_grants_enabled,
            "rootUrl": self.root_url,
            "defaultClientScopes": self.default_client_scopes,
            "optionalClientScopes": self.optional_client_scopes,
            "attributes": {
                "backchannel.logout.session.required": "true",
                "use.refresh.tokens": "true",
            },
        }


class OIDCTestClient:
    """Wrapper for OIDC client with testing utilities"""

    def __init__(self, keycloak_oidc_client: KeycloakOpenID):
        self.oidc_client = keycloak_oidc_client

    def get_token(self, username: str, password: str) -> Token:
        """Get access token for user credentials"""
        token_data = self.oidc_client.token(username, password)
        return Token(
            token_data["access_token"],
            self._create_refresh_func(),
            token_data.get("refresh_token", ""),
        )

    def get_service_account_token(self) -> Token:
        """Get service account token (for confidential clients)"""
        token_data = self.oidc_client.token(grant_type="client_credentials")
        return Token(
            token_data["access_token"],
            self._create_refresh_func(),
            token_data.get("refresh_token", ""),
        )

    def get_auth(self, username: str, password: str, location: str = "authorization") -> HttpxOidcClientAuth:
        """Get HttpxOidcClientAuth for testing"""
        token = self.get_token(username, password)
        return HttpxOidcClientAuth(token, location)

    def create_provider_config(self, oidc_provider) -> Provider:
        """Create Provider configuration for OIDC policy"""
        return Provider(
            issuerURL=oidc_provider.well_known["issuer"],
            clientID=self.oidc_client.client_id,
            authorizationEndpoint=oidc_provider.well_known["authorization_endpoint"],
            tokenEndpoint=oidc_provider.well_known["token_endpoint"],
        )

    def _create_refresh_func(self):
        """Create refresh token function"""

        def refresh_token_func(refresh_token: str) -> Token:
            new_token_data = self.oidc_client.refresh_token(refresh_token)
            return Token(
                new_token_data["access_token"],
                refresh_token_func,
                new_token_data.get("refresh_token", ""),
            )

        return refresh_token_func

    @classmethod
    def create_confidential_client(cls, keycloak, hostname: str, client_id: str = "my-confidential-client"):
        """Factory method for confidential client"""
        config = ClientConfig(
            client_id=client_id,
            client_type="confidential",
            public_client=False,
            redirect_uris=[f"http://{hostname}/*"],
            web_origins=[f"http://{hostname}"],
            root_url=f"http://{hostname}",
            service_accounts_enabled=True,
        )

        keycloak_client = keycloak.realm.create_client(**config.to_keycloak_payload())

        oidc_client = KeycloakOpenID(
            server_url=keycloak.server_url,
            client_id=keycloak_client.auth_id,
            realm_name=keycloak.realm_name,
            client_secret_key=keycloak_client.secret,
        )

        return cls(oidc_client)

    @classmethod
    def create_public_client(cls, keycloak, hostname: str, client_id: str = "my-public-client"):
        """Factory method for public client"""
        config = ClientConfig(
            client_id=client_id,
            client_type="public",
            public_client=True,
            redirect_uris=[f"http://{hostname}/*"],
            web_origins=[f"http://{hostname}"],
            root_url=f"http://{hostname}",
            service_accounts_enabled=False,
        )

        keycloak_client = keycloak.realm.create_client(**config.to_keycloak_payload())

        oidc_client = KeycloakOpenID(
            server_url=keycloak.server_url,
            client_id=keycloak_client.auth_id,
            realm_name=keycloak.realm_name,
        )

        return cls(oidc_client)

    @classmethod
    def create_service_client(cls, keycloak, hostname: str, client_id: str = "my-service-client"):
        """Factory method for service account client"""
        config = ClientConfig(
            client_id=client_id,
            client_type="service",
            public_client=False,
            standard_flow_enabled=False,
            service_accounts_enabled=True,
            redirect_uris=[f"http://{hostname}/*"],
            web_origins=[f"http://{hostname}"],
            root_url=f"http://{hostname}",
            direct_access_grants_enabled=False,
        )

        keycloak_client = keycloak.realm.create_client(**config.to_keycloak_payload())

        oidc_client = KeycloakOpenID(
            server_url=keycloak.server_url,
            client_id=keycloak_client.auth_id,
            realm_name=keycloak.realm_name,
            client_secret_key=keycloak_client.secret,
        )

        return cls(oidc_client)
