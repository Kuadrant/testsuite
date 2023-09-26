"""Envoy Gateway module"""
import time
from importlib import resources
from typing import Optional

import openshift as oc

from testsuite.certificates import Certificate
from testsuite.objects.gateway import Gateway
from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift.objects.envoy.config import EnvoyConfig


class Envoy(Gateway):  # pylint: disable=too-many-instance-attributes
    """Envoy deployed from template"""

    @property
    def reference(self) -> dict[str, str]:
        raise AttributeError("Not Supported for Envoy-only deployment")

    def __init__(self, openshift: "OpenShiftClient", name, authorino, image, labels: dict[str, str]) -> None:
        self._openshift = openshift
        self.authorino = authorino
        self.name = name
        self.image = image
        self.labels = labels
        self.template = resources.files("testsuite.resources").joinpath("envoy.yaml")
        self._config = None
        self.envoy_objects: oc.Selector = None  # type: ignore

    @property
    def config(self):
        """Returns EnvoyConfig instance"""
        if not self._config:
            self._config = EnvoyConfig.create_instance(self.openshift, self.name, self.authorino, self.labels)
        return self._config

    @property
    def app_label(self):
        """Returns App label that should be applied to all resources"""
        return self.labels.get("app")

    @property
    def openshift(self) -> "OpenShiftClient":
        return self._openshift

    @property
    def service_name(self) -> str:
        return self.name

    def rollout(self):
        """Restarts Envoy to apply newest config changes"""
        self.openshift.do_action("rollout", ["restart", f"deployment/{self.name}"])
        self.wait_for_ready()
        time.sleep(3)  # or some reason wait_for_ready is not enough, needs more investigation

    def wait_for_ready(self, timeout: int = 180):
        with oc.timeout(timeout):
            assert self.openshift.do_action(
                "rollout", ["status", f"deployment/{self.name}"]
            ), "Envoy wasn't ready in time"

    def commit(self):
        """Deploy all required objects into OpenShift"""
        self.config.commit()
        self.envoy_objects = self.openshift.new_app(
            self.template,
            {
                "NAME": self.name,
                "LABEL": self.app_label,
                "ENVOY_IMAGE": self.image,
            },
        )

    def get_tls_cert(self) -> Optional[Certificate]:
        return None

    def delete(self):
        """Destroy all objects this instance created"""
        self.config.delete()
        self._config = None
        with self.openshift.context:
            if self.envoy_objects:
                self.envoy_objects.delete()
        self.envoy_objects = None
