"""Limitador CR object"""

from openshift_client import selector

from testsuite.kubernetes import CustomResource
from testsuite.kubernetes.deployment import Deployment


class LimitadorCR(CustomResource):
    """Represents Limitador CR objects"""

    @property
    def deployment(self) -> Deployment:
        """Returns Deployment object for this Limitador"""
        with self.context:
            return selector(f"deployment/{self.name()}").object(cls=Deployment)
