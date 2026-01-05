"""Kuadrant CR"""

import dataclasses
from dataclasses import dataclass
from typing import Optional

from openshift_client import selector

from testsuite.kuadrant.authorino import Authorino, AuthorinoCR
from testsuite.kuadrant.limitador import LimitadorCR
from testsuite.kubernetes import CustomResource, modify
from testsuite.kubernetes.deployment import Deployment
from testsuite.utils import asdict


@dataclass
class ObservabilityTracingOptions:
    """Dataclass for observability tracing configuration"""

    defaultEndpoint: str  # pylint: disable=invalid-name
    insecure: Optional[bool] = None


@dataclass
class DataPlaneDefaultLevels:
    """Dataclass for data plane default levels"""

    debug: str


@dataclass
class DataPlaneOptions:
    """Dataclass for data plane configuration"""

    defaultLevels: list[DataPlaneDefaultLevels]  # pylint: disable=invalid-name
    httpHeaderIdentifier: str  # pylint: disable=invalid-name


@dataclass
class ObservabilityOptions:
    """Dataclass for observability configuration"""

    enable: bool
    tracing: Optional[ObservabilityTracingOptions] = None
    dataPlane: Optional[DataPlaneOptions] = None  # pylint: disable=invalid-name


class KuadrantSection:
    """
    Base class for Kuadrant sub components:
        Authorino - spec.authorino
        Limitador - spec.limitador
    """

    def __init__(self, kuadrant_cr, spec_name):
        super().__init__()
        self.kuadrant_cr = kuadrant_cr
        self.spec_name = spec_name

    @property
    def deployment(self):
        """Returns Deployment object for CR"""
        with self.context:
            return selector("deployment", labels={"app": self.spec_name}).object(cls=Deployment)

    def name(self):
        """Overrides `name` method from `apiobject` so it returns name of Kuadrant section"""
        return self.spec_name

    def __getitem__(self, name):
        return self.kuadrant_cr.model.spec[self.spec_name][name]

    def __setitem__(self, name, value):
        if dataclasses.is_dataclass(value):
            self.kuadrant_cr.model.spec[self.spec_name][name] = asdict(value)
        else:
            self.kuadrant_cr.model.spec[self.spec_name][name] = value

    def __getattr__(self, item):
        try:
            return getattr(self.kuadrant_cr, item)
        except AttributeError as exc:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'") from exc


class KuadrantCR(CustomResource):
    """Represents Kuadrant CR objects"""

    @property
    def authorino(self) -> AuthorinoCR:
        """Returns associated default AuthorinoCR object"""
        with self.context:
            return selector("authorino").object(cls=AuthorinoCR)

    @modify
    def set_observability(self, observability):
        """Enable observability with optional configuration.

        Args:
            observability: Either a bool (simple enable/disable) or ObservabilityOptions
                         (full configuration with tracing, dataPlane, etc.)
        """
        if observability is False or observability is None:
            self.model.spec["observability"] = None
        elif observability is True:
            self.model.spec["observability"] = {"enable": True}
        else:
            self.model.spec["observability"] = asdict(observability)

    @property
    def limitador(self) -> LimitadorCR:
        """Returns associated default LimitadorCR object"""
        with self.context:
            return selector("limitador").object(cls=LimitadorCR)
