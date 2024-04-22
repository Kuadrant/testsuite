"""Classes related to Gateways"""

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, TYPE_CHECKING, Literal, List

from httpx import Client

from testsuite.certificates import Certificate
from testsuite.httpx import KuadrantClient
from testsuite.lifecycle import LifecycleObject
from testsuite.utils import asdict

if TYPE_CHECKING:
    from testsuite.openshift.client import OpenShiftClient
    from testsuite.backend import Backend


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


@dataclass
class HeadersMatch:
    """HTTPHeaderMatch describes how to select a HTTP route by matching HTTP request headers."""

    name: str
    value: str
    type: Optional[Literal[MatchType.EXACT, MatchType.REGULAR_EXPRESSION]] = None


@dataclass
class QueryParamsMatch:
    """HTTPQueryParamMatch describes how to select a HTTP route by matching HTTP query parameters."""

    name: str
    value: str
    type: Optional[Literal[MatchType.EXACT, MatchType.REGULAR_EXPRESSION]] = None


@dataclass
class RouteMatch:
    """
    HTTPRouteMatch defines the predicate used to match requests to a given action.
    Multiple match types are ANDed together, i.e. the match will evaluate to true only if all conditions are satisfied.
    https://gateway-api.sigs.k8s.io/reference/spec/#gateway.networking.k8s.io/v1.HTTPRouteMatch
    """

    path: Optional[PathMatch] = None
    headers: Optional[List[HeadersMatch]] = None
    query_params: Optional[List[QueryParamsMatch]] = None
    method: Optional[HTTPMethod] = None


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
    def external_ip(self) -> str:
        """Returns loadBalanced IP and port to access this Gateway"""

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
    def add_backend(self, backend: "Backend", prefix):
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
    def client(self, **kwargs) -> KuadrantClient:
        """Return Httpx client for the requests to this backend"""

    @property
    @abstractmethod
    def hostname(self) -> str:
        """Returns full hostname in string form associated with this object"""


class Exposer(LifecycleObject):
    """Exposes hostnames to be accessible from outside"""

    def __init__(self, openshift):
        super().__init__()
        self.openshift = openshift
        self.passthrough = False
        self.verify = None

    @abstractmethod
    def expose_hostname(self, name, gateway: Gateway) -> Hostname:
        """
        Exposes hostname, so it is accessible from outside
        Actual hostname is generated from "name" and is returned in a form of a Hostname object
        """

    @property
    @abstractmethod
    def base_domain(self) -> str:
        """Returns base domains for all hostnames created by this exposer"""
