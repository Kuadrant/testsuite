"""Module containing base classes for common objects"""
import abc
from dataclasses import dataclass, is_dataclass, fields, replace
from copy import deepcopy
from typing import Literal, Union

JSONValues = Union[None, str, int, bool, list["JSONValues"], dict[str, "JSONValues"]]


def asdict(obj, ignore_overwrite=False) -> dict[str, JSONValues]:
    """
    This function converts dataclass object to dictionary.
    While it works similar to `dataclasses.asdict` a notable change is usage of overriding `asdict_override()` function
    if dataclass contains it and `ignore_overwrite` is set to False (it is by default).
    This function works recursively in lists, tuples and dicts. All other values are passed to copy.deepcopy function.
    """
    if not is_dataclass(obj):
        raise TypeError("asdict() should be called on dataclass instances")
    return _asdict_recurse(obj, ignore_overwrite)


def _asdict_recurse(obj, ignore_overwrite=False):
    if hasattr(obj, "asdict_override") and not ignore_overwrite:
        return obj.asdict_override()

    if not is_dataclass(obj):
        return deepcopy(obj)

    result = {}
    for field in fields(obj):
        value = getattr(obj, field.name)
        if value is None:
            continue  # do not include None values

        if is_dataclass(value):
            result[field.name] = _asdict_recurse(value)
        elif isinstance(value, (list, tuple)):
            result[field.name] = type(value)(_asdict_recurse(i) for i in value)
        elif isinstance(value, dict):
            result[field.name] = type(value)((_asdict_recurse(k), _asdict_recurse(v)) for k, v in value.items())
        else:
            result[field.name] = deepcopy(value)
    return result


def asdict_compose(obj):
    """
    Helper asdict function for classes which use class composition and want to keep flat dictionary structure.
    This removes the key under which the dataclass object was stored under and replaces it with
    the dictionary view of the dataclass object.
    For use in asdict_override() function.
    """
    obj_copy = replace(obj)
    result = {}
    for field in fields(obj_copy):
        if is_dataclass(field):
            result.update(asdict(field))
            delattr(obj_copy, field.name)
    result.update(asdict(obj_copy, ignore_overwrite=True))
    return result


@dataclass
class MatchExpression:
    """
    Data class intended for defining K8 Label Selector expressions.
    Used by selector.matchExpressions API key identity.
    """

    operator: Literal["In", "NotIn", "Exists", "DoesNotExist"]
    values: list[str]
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


@dataclass
class ABCValue(abc.ABC):
    """
    Abstract Dataclass for specifying a Value in Authorization,
    can be either static or reference to value in AuthJson.
    """


@dataclass
class Value(ABCValue):
    """Dataclass for static Value. Can be any value allowed in JSON: None, string, integer, bool, list, dict"""

    value: JSONValues


@dataclass
class ValueFrom(ABCValue):
    """Dataclass for dynamic Value. It contains reference path to existing value in AuthJson."""

    authJSON: str  # pylint: disable=invalid-name

    def asdict_override(self):
        """Override `asdict` function"""
        return {"valueFrom": {"authJSON": self.authJSON}}


@dataclass
class Property:
    """Dataclass for static and dynamic values. Property is a Value with name."""

    name: str
    value: ABCValue

    def asdict_override(self):
        """Override `asdict` function"""
        return asdict_compose(self)


@dataclass
class Cache:
    """Dataclass for specifying Cache in Authorization"""

    ttl: int
    key: ABCValue


@dataclass
class PatternRef:
    """Dataclass for specifying Pattern reference in Authorization"""

    patternRef: str  # pylint: disable=invalid-name


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
