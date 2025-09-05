"""Module containing classes related to OIDCPolicy"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Optional

from enum import Enum, auto
from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy
from testsuite.utils import asdict


@dataclass
class Provider:
    """Provider defines the settings related to the Identity Provider (IDP)"""

    issuer_url: str
    client_id: str
    client_secret: Optional[str] = None
    authorization_endpoint: Optional[str] = None
    redirect_uri: Optional[str] = None
    token_endpoint: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for Kubernetes manifest"""
        result = {
            "issuerURL": self.issuer_url,
            "clientID": self.client_id,
        }
        if self.client_secret:
            result["clientSecret"] = self.client_secret
        if self.authorization_endpoint:
            result["authorizationEndpoint"] = self.authorization_endpoint
        if self.redirect_uri:
            result["redirectURI"] = self.redirect_uri
        if self.token_endpoint:
            result["tokenEndpoint"] = self.token_endpoint
        return result


class CredentialsType(Enum):
    """Enum for credential types"""

    UNKNOWN = auto()
    AUTHORIZATION_HEADER = auto()
    CUSTOM_HEADER = auto()
    QUERY_STRING = auto()
    COOKIE = auto()


@dataclass
class Named:
    """Named represents a credential with a name"""

    name: str

    def to_dict(self) -> Dict:
        return {"name": self.name}


@dataclass
class Prefixed:
    """Prefixed represents a credential with a prefix"""

    prefix: Optional[str] = None

    def to_dict(self) -> Dict:
        result = {}
        if self.prefix:
            result["prefix"] = self.prefix
        return result


@dataclass
class CustomHeader(Named):
    """CustomHeader represents a named header credential"""

    def to_dict(self) -> Dict:
        return super().to_dict()


@dataclass
class Credentials:
    """Credentials configuration for token source"""

    authorization_header: Optional[Prefixed] = None
    custom_header: Optional[CustomHeader] = None
    query_string: Optional[Named] = None
    cookie: Optional[Named] = None

    def get_type(self) -> CredentialsType:
        """Get the type of credentials being used"""
        if self.authorization_header is not None:
            return CredentialsType.AUTHORIZATION_HEADER
        if self.custom_header is not None:
            return CredentialsType.CUSTOM_HEADER
        if self.query_string is not None:
            return CredentialsType.QUERY_STRING
        if self.cookie is not None:
            return CredentialsType.COOKIE
        return CredentialsType.UNKNOWN

    def to_dict(self) -> Dict:
        """Convert to dictionary for Kubernetes manifest"""
        result = {}
        if self.authorization_header:
            result["authorizationHeader"] = self.authorization_header.to_dict()
        if self.custom_header:
            result["customHeader"] = self.custom_header.to_dict()
        if self.query_string:
            result["queryString"] = self.query_string.to_dict()
        if self.cookie:
            result["cookie"] = self.cookie.to_dict()
        return result


@dataclass
class Auth:
    """Auth holds the information regarding AuthN/AuthZ"""

    token_source: Optional[Credentials] = None
    claims: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for Kubernetes manifest"""
        result = {}
        if self.token_source:
            result["tokenSource"] = self.token_source.to_dict()
        if self.claims:
            result["claims"] = self.claims
        return result


class OIDCPolicy(Policy):
    """OIDCPolicy object, it serves as Kuadrant's OIDC configuration"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def create_instance(
        cls,
        cluster: KubernetesClient,
        name: str,
        target: Referencable,
        provider: Provider,
        auth: Optional[Auth] = None,
        labels: Dict[str, str] = None,
        section_name: str = None,
    ):
        """Creates base instance"""
        model: Dict = {
            "apiVersion": "extensions.kuadrant.io/v1alpha1",
            "kind": "OIDCPolicy",
            "metadata": {"name": name, "namespace": cluster.project, "labels": labels},
            "spec": {
                "targetRef": target.reference,
                "provider": provider.to_dict(),
            },
        }
        if auth:
            model["spec"]["auth"] = auth.to_dict()
        if section_name:
            model["spec"]["targetRef"]["sectionName"] = section_name

        return cls(model, context=cluster.context)

    @modify
    def set_provider(self, provider: Provider) -> None:
        """Set the OIDC provider configuration"""
        self.model.spec["provider"] = provider.to_dict()

    @modify
    def set_auth(self, auth: Auth) -> None:
        """Set the authentication configuration"""
        self.model.spec["auth"] = auth.to_dict()

    @modify
    def set_claims(self, claims: Dict[str, str]) -> None:
        """Set the JWT claims requirements"""
        if "auth" not in self.model.spec:
            self.model.spec["auth"] = {}
        self.model.spec["auth"]["claims"] = claims

    @modify
    def set_token_source(self, token_source: Dict) -> None:
        """Set the token source configuration"""
        if "auth" not in self.model.spec:
            self.model.spec["auth"] = {}
        self.model.spec["auth"]["tokenSource"] = token_source
