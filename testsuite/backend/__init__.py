"""Module containing all the Backends"""

from abc import abstractmethod

from testsuite.gateway import Referencable
from testsuite.lifecycle import LifecycleObject


class Backend(LifecycleObject, Referencable):
    """Backend (workload) deployed in Kubernetes"""

    @property
    @abstractmethod
    def url(self):
        """Returns internal URL for this backend"""
