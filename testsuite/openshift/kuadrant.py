"""Kuadrant CR object"""

from openshift_client import selector

from testsuite.openshift import OpenShiftObject, modify


class KuadrantCR(OpenShiftObject):
    """Represents Kuadrant CR objects"""

    LIMITADOR = "limitador-limitador"

    @modify
    def set_limitador(self, replicas: dict):
        """Configure Limitador spec"""
        self.model.spec.setdefault("limitador", {})
        self.model.spec["limitador"] = replicas

    def delete(self, ignore_not_found=True, cmd_args=None):
        """Don't delete please."""
        raise TypeError("Don't delete Kuadrant CR")

    @property
    def limitador_deployment(self):
        """Returns Deployment object for this Authorino"""
        with self.context:
            return selector(f"deployment/{self.LIMITADOR}").object()
