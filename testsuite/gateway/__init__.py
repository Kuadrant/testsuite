"""Classes related to Gateways"""
import abc
import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, TYPE_CHECKING, Literal, List

from httpx import Client

from testsuite.certificates import Certificate
from testsuite.lifecycle import LifecycleObject
from testsuite.utils import asdict, _asdict_recurse

if TYPE_CHECKING:
    from testsuite.openshift.client import OpenShiftClient
    from testsuite.openshift.httpbin import Httpbin


class Referencable(ABC):
    """Object that can be referenced in Gateway API style"""

    @property
    @abstractmethod
    def reference(self) -> dict[str, str]:
        """
        Returns dict, which can be used as reference in Gateway API Objects.
        https://gateway-api.sigs.k8s.io/references/spec/#gateway.networking.k8s.io/v1beta1.ParentReference
        """


@dataclass
class CustomReference(Referencable):
    """
    Manually creates Reference object.
    https://gateway-api.sigs.k8s.io/references/spec/#gateway.networking.k8s.io%2fv1beta1.ParentReference
    """

    @property
    def reference(self) -> dict[str, Any]:
        return asdict(self)

    group: str
    kind: str
    name: str
    namespace: Optional[str] = None
    sectionName: Optional[str] = None  # pylint: disable=invalid-name
    port: Optional[int] = None


class HTTPMethod(enum.Enum):
    """HTTP methods supported by Matchers"""

    CONNECT = "CONNECT"
    DELETE = "DELETE"
    GET = "GET"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    PATCH = "PATCH"
    POST = "POST"
    PUT = "PUT"
    TRACE = "TRACE"


class MatchType(enum.Enum):
    """MatchType specifies the semantics of how HTTP header values should be compared."""

    EXACT = "Exact"
    PATH_PREFIX = "PathPrefix"
    REGULAR_EXPRESSION = "RegularExpression"


@dataclass
class PathMatch:
    """HTTPPathMatch describes how to select an HTTP route by matching the HTTP request path."""

    type: Optional[MatchType] = None
    value: Optional[str] = None

    # def asdict(self):
    #     """Custom dict due to nested structure of matchers."""
    #     return {"path": _asdict_recurse(self, False)}


@dataclass
class HeadersMatch:
    """HTTPHeaderMatch describes how to select a HTTP route by matching HTTP request headers."""

    name: str
    value: str
    type: Optional[Literal[MatchType.EXACT, MatchType.REGULAR_EXPRESSION]] = None

    # def asdict(self):
    #     """Custom dict due to nested structure of matchers."""
    #     return {"headers": [_asdict_recurse(self, False)]}


@dataclass
class QueryParamsMatch:
    """HTTPQueryParamMatch describes how to select a HTTP route by matching HTTP query parameters."""

    name: str
    value: str
    type: Optional[Literal[MatchType.EXACT, MatchType.REGULAR_EXPRESSION]] = None

    # def asdict(self):
    #     """Custom dict due to nested structure of matchers."""
    #     return {"queryParams": [_asdict_recurse(self, False)]}


@dataclass
class MethodMatch:
    """
    HTTPMethod describes how to select a HTTP route by matching the HTTP method. The value is expected in upper case.
    """

    value: HTTPMethod = None

    def asdict(self):
        """Custom dict due to nested structure of matchers."""
        return {"method": self.value.value}


@dataclass
class RouteMatch:
    """
    Abstract Dataclass for HTTPRouteMatch.
    API specification consists of two layers: HTTPRouteMatch which can contain 4 matchers (see offsprings).
    We merged this to a single Matcher representation for simplicity, which is why we need custom `asdict` methods.
    https://gateway-api.sigs.k8s.io/reference/spec/#gateway.networking.k8s.io/v1.HTTPRouteMatch
    """

    path: Optional[PathMatch] = None
    headers: Optional[List[HeadersMatch]] = None
    query_params: Optional[List[QueryParamsMatch]] = None
    method: HTTPMethod = None


class Gateway(LifecycleObject, Referencable):
    """
    Abstraction layer for a Gateway sitting between end-user and Kuadrant
    Simplified: Equals to Gateway Kubernetes object
    """

    @property
    @abstractmethod
    def openshift(self) -> "OpenShiftClient":
        """Returns OpenShift client for this gateway"""

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Service name for this gateway"""

    @abstractmethod
    def wait_for_ready(self, timeout: int = 90):
        """Waits until the gateway is ready"""

    @abstractmethod
    def get_tls_cert(self) -> Optional[Certificate]:
        """Returns TLS cert bound to this Gateway, if the Gateway does not use TLS, returns None"""


class GatewayRoute(LifecycleObject, Referencable):
    """
    Abstraction layer for *Route objects in Gateway API
    Simplified: Equals to HTTPRoute Kubernetes object
    """

    @classmethod
    @abstractmethod
    def create_instance(
        cls,
        openshift: "OpenShiftClient",
        name,
        gateway: Gateway,
        labels: dict[str, str] = None,
    ):
        """Creates new gateway instance"""

    @abstractmethod
    def add_hostname(self, hostname: str):
        """Adds hostname to the Route"""

    @abstractmethod
    def remove_hostname(self, hostname: str):
        """Remove hostname from the Route"""

    @abstractmethod
    def remove_all_hostnames(self):
        """Remove all hostnames from the Route"""

    @abstractmethod
    def add_backend(self, backend: "Httpbin", prefix):
        """Adds another backend to the Route, with specific prefix"""

    @abstractmethod
    def remove_all_backend(self):
        """Sets match for a specific backend"""


class Hostname(ABC):
    """
    Abstraction layer on top of externally exposed hostname
    Simplified: Does not have any equal Kubernetes object. It is a hostname you can send HTTP request to
    """

    @abstractmethod
    def client(self, **kwargs) -> Client:
        """Return Httpx client for the requests to this backend"""

    @property
    @abstractmethod
    def hostname(self) -> str:
        """Returns full hostname in string form associated with this object"""


class Exposer:
    """Exposes hostnames to be accessible from outside"""

    @abstractmethod
    def expose_hostname(self, name, gateway: Gateway) -> Hostname:
        """
        Exposes hostname, so it is accessible from outside
        Actual hostname is generated from "name" and is returned in a form of a Hostname object
        """
