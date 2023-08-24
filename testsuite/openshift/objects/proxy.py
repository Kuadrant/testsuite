"""Module containing Proxy related stuff"""
from abc import abstractmethod

from testsuite.objects import LifecycleObject
from testsuite.openshift.objects.route import Route


class Proxy(LifecycleObject):
    """Abstraction layer for a Proxy sitting between end-user and Kuadrant"""

    @abstractmethod
    def expose_hostname(self, name) -> Route:
        """Exposes hostname to point to this Proxy"""
