"""Module containing classes related to OIDCPolicy"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Optional
from testsuite.gateway import Referencable
from testsuite.kubernetes import modify
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy
from testsuite.utils import asdict


@dataclass
class Provider:
    """Provider defines the settings related to the Identity Provider (IDP)"""

    issuerURL: str  # pylint: disable=invalid-name
    clientID: str  # pylint: disable=invalid-name
    clientSecret: Optional[str] = None  # pylint: disable=invalid-name
    authorizationEndpoint: Optional[str] = None  # pylint: disable=invalid-name
    redirectURI: Optional[str] = None  # pylint: disable=invalid-name
    tokenEndpoint: Optional[str] = None  # pylint: disable=invalid-name


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


@dataclass
class Prefixed:
    """Prefixed represents a credential with a prefix"""

    prefix: Optional[str] = None


@dataclass
class CustomHeader(Named):
    """CustomHeader represents a named header credential"""

    pass


@dataclass
class Credentials:
    """Credentials configuration for token source"""

    authorizationHeader: Optional[Prefixed] = None  # pylint: disable=invalid-name
    customHeader: Optional[CustomHeader] = None  # pylint: disable=invalid-name
    queryString: Optional[Named] = None  # pylint: disable=invalid-name
    cookie: Optional[Named] = None

    def get_type(self) -> CredentialsType:
        """Get the type of credentials being used"""
        if self.authorizationHeader is not None:
            return CredentialsType.AUTHORIZATION_HEADER
        if self.customHeader is not None:
            return CredentialsType.CUSTOM_HEADER
        if self.queryString is not None:
            return CredentialsType.QUERY_STRING
        if self.cookie is not None:
            return CredentialsType.COOKIE
        return CredentialsType.UNKNOWN


@dataclass
class Auth:
    """Auth holds the information regarding AuthN/AuthZ"""

    tokenSource: Optional[Credentials] = None  # pylint: disable=invalid-name
    claims: Optional[Dict[str, str]] = None


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
                "provider": asdict(provider),
            },
        }
        if auth:
            model["spec"]["auth"] = asdict(auth)
        if section_name:
            model["spec"]["targetRef"]["sectionName"] = section_name

        return cls(model, context=cluster.context)

    @modify
    def set_provider(self, provider: Provider) -> None:
        """Set the OIDC provider configuration"""
        self.model.spec["provider"] = asdict(provider)

    @modify
    def set_auth(self, auth: Auth) -> None:
        """Set the authentication configuration"""
        self.model.spec["auth"] = asdict(auth)

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
