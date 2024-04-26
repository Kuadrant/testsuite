"""Kuadrant CR object"""

from openshift_client import selector

from testsuite.openshift import OpenShiftObject, modify
from testsuite.openshift.deployment import Deployment


class KuadrantCR(OpenShiftObject):
    """Represents Kuadrant CR objects"""

    LIMITADOR = "limitador-limitador"

    @property
    def limitador(self) -> dict:
        """Returns spec.limitador from Kuadrant object"""
        return self.model.spec.setdefault("limitador", {})

    @limitador.setter
    @modify
    def limitador(self, value: dict):
        """Sets the value of spec.limitador"""
        self.model.spec["limitador"] = value

    @property
    def limitador_deployment(self):
        """Returns Deployment object for this Authorino"""
        with self.context:
            return selector(f"deployment/{self.LIMITADOR}").object(cls=Deployment)
