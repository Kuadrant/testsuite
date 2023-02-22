"""Contains implementation for all AuthConfig sections"""
import abc

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from testsuite.objects import Rule, Value


class Authorizations(abc.ABC):
    """Authorization configuration"""

    @abc.abstractmethod
    def opa_policy(self, name, rego_policy, **common_features):
        """Adds OPA inline Rego policy"""

    @abc.abstractmethod
    def external_opa_policy(self, name, endpoint, ttl, **common_features):
        """Adds OPA policy from external registry"""

    @abc.abstractmethod
    def role_rule(self, name: str, role: str, path: str, **common_features):
        """Adds a rule, which allows access to 'path' only to users with 'role'"""

    @abc.abstractmethod
    def auth_rule(self, name: str, rule: "Rule", **common_features):
        """Adds JSON pattern-matching authorization rule (authorization.json)"""

    @abc.abstractmethod
    def kubernetes(self, name: str, user: "Value", kube_attrs: dict, **common_features):
        """Adds kubernetes authorization rule."""


class Identities(abc.ABC):
    """Identities configuration"""

    @abc.abstractmethod
    def oidc(self, name, endpoint, credentials, selector, **common_features):
        """Adds OIDC identity provider"""

    @abc.abstractmethod
    def api_key(self, name, all_namespaces, match_label, match_expression, credentials, selector, **common_features):
        """Adds API Key identity"""

    @abc.abstractmethod
    def mtls(self, name: str, selector_key: str, selector_value: str, **common_features):
        """Adds mTLS identity"""

    @abc.abstractmethod
    def anonymous(self, name, **common_features):
        """Adds anonymous identity"""

    @abc.abstractmethod
    def kubernetes(self, name, auth_json, **common_features):
        """Adds kubernetes identity"""

    @abc.abstractmethod
    def remove_all(self):
        """Removes all identities from AuthConfig"""


class Metadata(abc.ABC):
    """Metadata configuration"""

    @abc.abstractmethod
    def http_metadata(self, name, endpoint, method, **common_features):
        """Set metadata http external auth feature"""

    @abc.abstractmethod
    def user_info_metadata(self, name, identity_source, **common_features):
        """Set metadata OIDC user info"""

    @abc.abstractmethod
    def uma_metadata(self, name, endpoint, credentials, **common_features):
        """Set metadata User-Managed Access (UMA) resource registry"""


class Responses(abc.ABC):
    """Responses configuration"""

    @abc.abstractmethod
    def add(self, response, **common_features):
        """Add response to AuthConfig"""
