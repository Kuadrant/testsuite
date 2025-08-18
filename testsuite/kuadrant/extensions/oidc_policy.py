"""Module containing classes related to OIDCPolicy"""

from dataclasses import dataclass
from typing import Dict, Optional
from testsuite.gateway import Referencable
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kuadrant.policy import Policy
from testsuite.utils import asdict


@dataclass
class Provider:  # pylint: disable=invalid-name
    """Provider defines the settings related to the Identity Provider (IDP)"""

    issuerURL: str
    clientID: str
    authorizationEndpoint: Optional[str] = None
    redirectURI: Optional[str] = None
    tokenEndpoint: Optional[str] = None


@dataclass
class Auth:  # pylint: disable=invalid-name
    """Auth holds the information regarding AuthN/AuthZ"""

    tokenSource: Optional[Dict[str, str]] = None
    claims: Optional[Dict[str, str]] = None


class OIDCPolicy(Policy):
    """OIDCPolicy object, it serves as Kuadrant's OIDC configuration"""

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
