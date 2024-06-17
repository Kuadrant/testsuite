"""Kuadrant CR object"""

import dataclasses

from openshift_client import selector

from testsuite.openshift import CustomResource
from testsuite.openshift.deployment import Deployment
from testsuite.utils import asdict


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

    LIMITADOR = "limitador-limitador"

    @property
    def authorino(self) -> KuadrantSection:
        """Returns spec.authorino from Kuadrant object"""
        self.model.spec.setdefault("authorino", {})
        return KuadrantSection(self, "authorino")

    @property
    def limitador(self) -> KuadrantSection:
        """Returns spec.limitador from Kuadrant object"""
        self.model.spec.setdefault("limitador", {})
        return KuadrantSection(self, "limitador")

    @property
    def limitador_deployment(self):
        """Returns Deployment object for this Authorino"""
        with self.context:
            return selector(f"deployment/{self.LIMITADOR}").object(cls=Deployment)
