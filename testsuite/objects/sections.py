"""Contains implementation for all AuthConfig sections"""
import abc

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from testsuite.objects import Rule


class Authorizations(abc.ABC):
    """Authorization configuration"""

    @abc.abstractmethod
    def opa_policy(self, name, rego_policy):
        """Adds OPA inline Rego policy"""

    @abc.abstractmethod
    def external_opa_policy(self, name, endpoint, ttl):
        """Adds OPA policy from external registry"""

    @abc.abstractmethod
    def role_rule(self, name: str, role: str, path: str, metrics: bool, priority: int):
        """Adds a rule, which allows access to 'path' only to users with 'role'"""

    @abc.abstractmethod
    def auth_rule(self, name: str, rule: "Rule", when: "Rule", metrics: bool, priority: int):
        """Adds JSON pattern-matching authorization rule (authorization.json)"""


class Identities(abc.ABC):
    """Identities configuration"""

    @abc.abstractmethod
    def oidc(self, name, endpoint, credentials, selector):
        """Adds OIDC identity provider"""

    @abc.abstractmethod
    def api_key(self, name, all_namespaces, match_label, match_expression, credentials, selector):
        """Adds API Key identity"""

    @abc.abstractmethod
    def mtls(self, name: str, selector_key: str, selector_value: str):
        """Adds mTLS identity"""

    @abc.abstractmethod
    def anonymous(self, name):
        """Adds anonymous identity"""

    @abc.abstractmethod
    def remove_all(self):
        """Removes all identities from AuthConfig"""


class Metadata(abc.ABC):
    """Metadata configuration"""

    @abc.abstractmethod
    def http_metadata(self, name, endpoint, method):
        """Set metadata http external auth feature"""

    @abc.abstractmethod
    def user_info_metadata(self, name, identity_source):
        """Set metadata OIDC user info"""

    @abc.abstractmethod
    def uma_metadata(self, name, endpoint, credentials):
        """Set metadata User-Managed Access (UMA) resource registry """


class Responses(abc.ABC):
    """Responses configuration"""

    @abc.abstractmethod
    def add(self, response):
        """Add response to AuthConfig"""
