"""Module containing base classes for common objects"""
import abc
from dataclasses import dataclass
from functools import cached_property
from typing import Literal, List

from testsuite.objects.sections import Metadata, Identities, Authorizations, Responses


@dataclass
class MatchExpression:
    """
    Data class intended for defining K8 Label Selector expressions.
    Used by selector.matchExpressions API key identity.
    """

    operator: Literal["In", "NotIn", "Exists", "DoesNotExist"]
    values: List[str]
    key: str = "group"


@dataclass
class Rule:
    """
    Data class for rules represented by simple pattern-matching expressions.
    Args:
        :param selector: that is fetched from the Authorization JSON
        :param operator: `eq` (equals), `neq` (not equal), `incl` (includes) and `excl` (excludes), for arrays
                         `matches`, for regular expressions
        :param value: a fixed comparable value
    """

    selector: str
    operator: Literal["eq", "neq", "incl", "excl", "matches"]
    value: str


class Value:
    """Dataclass for specifying a Value in Authorization, can be either constant or value from AuthJson (jsonPath)"""

    # pylint: disable=invalid-name
    def __init__(self, value=None, jsonPath=None) -> None:
        super().__init__()
        if not (value is None) ^ (jsonPath is None):
            raise AttributeError("Exactly one of the `value` and `jsonPath` argument must be specified")
        self.value = value
        self.jsonPath = jsonPath

    def to_dict(self):
        """Returns dict representation of itself (shallow copy only)"""
        return {"value": self.value} if self.value else {"valueFrom": {"authJson": self.jsonPath}}


@dataclass
class Cache:
    """Dataclass for specifying Cache in Authorization"""

    ttl: int
    key: Value

    def to_dict(self):
        """Returns dict representation of itself (shallow copy only)"""
        return {"ttl": self.ttl, "key": self.key.to_dict()}


@dataclass
class PatternRef:
    """Dataclass for specifying Pattern reference in Authorization"""

    # pylint: disable=invalid-name
    patternRef: str


class LifecycleObject(abc.ABC):
    """Any objects which has its lifecycle controlled by create() and delete() methods"""

    @abc.abstractmethod
    def commit(self):
        """Commits resource.
        if there is some reconciliation needed, the method should wait until it is all reconciled"""

    @abc.abstractmethod
    def delete(self):
        """Removes resource,
        if there is some reconciliation needed, the method should wait until it is all reconciled"""


class Authorino(LifecycleObject):
    """Authorino instance"""

    @abc.abstractmethod
    def wait_for_ready(self):
        """True, if after some waiting the Authorino is ready"""

    @property
    @abc.abstractmethod
    def authorization_url(self):
        """Authorization URL that can be plugged into envoy"""

    @property
    @abc.abstractmethod
    def oidc_url(self):
        """Authorino oidc url"""


class Authorization(LifecycleObject):
    """Object containing Authorization rules and configuration for either Authorino or Kuadrant"""

    @cached_property
    @abc.abstractmethod
    def authorization(self) -> Authorizations:
        """Gives access to authorization settings"""

    @cached_property
    @abc.abstractmethod
    def identity(self) -> Identities:
        """Gives access to identity settings"""

    @cached_property
    @abc.abstractmethod
    def metadata(self) -> Metadata:
        """Gives access to metadata settings"""

    @cached_property
    @abc.abstractmethod
    def responses(self) -> Responses:
        """Gives access to response settings"""

    @abc.abstractmethod
    def add_host(self, hostname):
        """Adds host"""

    @abc.abstractmethod
    def remove_host(self, hostname):
        """Remove host"""

    @abc.abstractmethod
    def remove_all_hosts(self):
        """Remove all hosts"""

    @abc.abstractmethod
    def set_deny_with(self, code, value):
        """Set denyWith"""

    @abc.abstractmethod
    def add_rule(self, when: list[Rule]):
        """Add rule for the skip of entire AuthConfig"""


class PreexistingAuthorino(Authorino):
    """Authorino which is already deployed prior to the testrun"""

    def __init__(self, authorization_url, oidc_url) -> None:
        super().__init__()
        self._authorization_url = authorization_url
        self._oidc_url = oidc_url

    def wait_for_ready(self):
        return True

    @property
    def authorization_url(self):
        return self._authorization_url

    @property
    def oidc_url(self):
        return self._oidc_url

    def commit(self):
        return

    def delete(self):
        return
