"""Abstract classes for Hostname related stuff"""
from abc import ABC, abstractmethod

from httpx import Client

from .gateway import Gateway


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
