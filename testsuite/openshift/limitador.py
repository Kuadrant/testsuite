"""Limitador CR object"""

from openshift_client import selector

from testsuite.openshift import OpenShiftObject, modify
from testsuite.openshift.authorino import TracingOptions
from testsuite.openshift.deployment import Deployment
from testsuite.utils import asdict


class LimitadorCR(OpenShiftObject):
    """Represents Limitador CR objects"""

    @property
    def deployment(self) -> Deployment:
        """Returns Deployment object for this Limitador"""
        with self.context:
            return selector("deployment/limitador-limitador").object(cls=Deployment)

    @property
    def tracing(self) -> dict:
        """Returns tracing config"""
        return self.model.spec.setdefault("tracing", {})

    @tracing.setter
    @modify
    def tracing(self, config: TracingOptions):
        """Sets tracing"""
        self.model.spec.setdefault("tracing", {})
        self.model.spec["tracing"] = asdict(config)

    @property
    def verbosity(self) -> int:
        """Returns verbosity config"""
        return self.model.spec.setdefault("verbosity", {})

    @verbosity.setter
    @modify
    def verbosity(self, level: int):
        """Sets verbosity"""
        self.model.spec.setdefault("verbosity", {})
        self.model.spec["verbosity"] = level
