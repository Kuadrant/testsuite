"""Authorization related objects"""
import abc
from dataclasses import dataclass, field
from typing import Literal, Optional
from testsuite.utils import asdict, JSONValues


# pylint: disable=invalid-name
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
class Selector:
    """Dataclass for specifying selectors based on either expression or labels"""

    matchExpressions: Optional[list[MatchExpression]] = field(default=None, kw_only=True)
    matchLabels: Optional[dict[str, str]] = field(default=None, kw_only=True)

    def __post_init__(self):
        if not (self.matchLabels is None) ^ (self.matchExpressions is None):
            raise AttributeError("`matchLabels` xor `matchExpressions` argument must be used")


@dataclass
class Credentials:
    """Dataclass for Credentials structure"""

    in_location: Literal["authorizationHeader", "customHeader", "queryString", "cookie"]
    keySelector: str

    def asdict(self):
        """Custom asdict because of needing to put location as parent dict key for inner dict"""
        if self.in_location == "authorizationHeader":
            return {self.in_location: {"prefix": self.keySelector}}
        return {self.in_location: {"name": self.keySelector}}


@dataclass
class Pattern:
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
class AnyPattern:
    """Dataclass specifying *OR* operation on patterns. Any one needs to pass for this block to pass."""

    any: list["Rule"]


@dataclass
class AllPattern:
    """Dataclass specifying *AND* operation on patterns. All need to pass for this block to pass."""

    all: list["Rule"]


@dataclass
class PatternRef:
    """
    Dataclass that references other pattern-matching expression by name.
    Use authorization.add_patterns() function to define named pattern-matching expression.
    """

    patternRef: str


Rule = Pattern | AnyPattern | AllPattern | PatternRef


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

    selector: str


@dataclass
class JsonResponse:
    """Response item as JSON injection."""

    properties: dict[str, ABCValue]

    def asdict(self):
        """Custom asdict due to nested structure."""
        asdict_properties = {}
        for key, value in self.properties.items():
            asdict_properties[key] = asdict(value)
        return {"json": {"properties": asdict_properties}}


@dataclass
class PlainResponse:
    """Response item as plain text value."""

    plain: ABCValue


@dataclass
class WristbandSigningKeyRef:
    """Name of Kubernetes secret and corresponding signing algorithm."""

    name: str
    algorithm: str = "RS256"


@dataclass(kw_only=True)
class WristbandResponse:
    """
    Response item as Festival Wristband Token.

    :param issuer: Endpoint to the Authorino service that issues the wristband
    :param signingKeyRefs: List of  Kubernetes secrets of dataclass `WristbandSigningKeyRef`
    :param customClaims: Custom claims added to the wristband token.
    :param tokenDuration: Time span of the wristband token, in seconds.
    """

    issuer: str
    signingKeyRefs: list[WristbandSigningKeyRef]
    customClaims: Optional[list[dict[str, ABCValue]]] = None
    tokenDuration: Optional[int] = None

    def asdict(self):
        """Custom asdict due to nested structure."""

        asdict_key_refs = [asdict(i) for i in self.signingKeyRefs]
        asdict_custom_claims = [asdict(i) for i in self.customClaims] if self.customClaims else None
        return {
            "wristband": {
                "issuer": self.issuer,
                "signingKeyRefs": asdict_key_refs,
                "customClaims": asdict_custom_claims,
                "tokenDuration": self.tokenDuration,
            }
        }


@dataclass(kw_only=True)
class DenyResponse:
    """Dataclass for custom responses deny reason."""

    code: Optional[int] = None
    message: Optional[ABCValue] = None
    headers: Optional[dict[str, ABCValue]] = None
    body: Optional[ABCValue] = None


@dataclass
class Cache:
    """Dataclass for specifying Cache in Authorization"""

    ttl: int
    key: ABCValue
