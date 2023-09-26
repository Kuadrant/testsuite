"""Module containing Proxy related stuff"""
from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Any

from . import LifecycleObject, asdict
from ..certificates import Certificate

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
