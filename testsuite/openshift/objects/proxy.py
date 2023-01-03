"""Module containing Proxy related stuff"""
from abc import abstractmethod
from functools import cached_property

from httpx import Client

from testsuite.objects import LifecycleObject
from testsuite.openshift.objects.route import Route


class Proxy(LifecycleObject):
    """Abstraction layer for a Proxy sitting between end-user and Authorino/Limitador"""

    @cached_property
    @abstractmethod
    def route(self) -> Route:
        """Returns default route for the proxy"""

    @abstractmethod
    def add_hostname(self, name) -> tuple[Route, str]:
        """Add another hostname that points to this Proxy"""

    @abstractmethod
    def client(self, **kwargs) -> Client:
        """Return Httpx client for the requests to this backend"""
