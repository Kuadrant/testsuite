"""Module containing Route related stuff"""
from abc import ABC, abstractmethod
from functools import cached_property

from testsuite.openshift.objects import OpenShiftObject


class Route(ABC):
    """Abstraction layer for Route/Ingress/HTTPRoute"""

    @cached_property
    @abstractmethod
    def hostname(self):
        """Returns Route hostname"""


class OpenshiftRoute(OpenShiftObject, Route):
    """Openshift Route object"""
    @cached_property
    def hostname(self):
        return self.model.spec.host
