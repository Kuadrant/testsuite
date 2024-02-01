"""Authorino CR object"""

import abc
from typing import Any, Dict, List

from openshift_client import selector, timeout

from testsuite.openshift.client import OpenShiftClient
from testsuite.openshift import OpenShiftObject
from testsuite.lifecycle import LifecycleObject


class Authorino(LifecycleObject):
    """Authorino interface"""

    @abc.abstractmethod
    def wait_for_ready(self):
        """True, if after some waiting the Authorino is ready"""

    @property
    @abc.abstractmethod
    def metrics_service(self):
        """Authorino metrics service name"""

    @property
    @abc.abstractmethod
    def authorization_url(self):
        """Authorization URL that can be plugged into envoy"""

    @property
    @abc.abstractmethod
    def oidc_url(self):
        """Authorino oidc url"""


class AuthorinoCR(OpenShiftObject, Authorino):
    """Represents Authorino CR objects from Authorino-operator"""

    @classmethod
    def create_instance(
        cls,
        openshift: OpenShiftClient,
        name,
        image=None,
        cluster_wide=False,
        label_selectors: List[str] = None,
        listener_certificate_secret=None,
        log_level=None,
    ):
        """Creates base instance"""
        model: Dict[str, Any] = {
            "apiVersion": "operator.authorino.kuadrant.io/v1beta1",
            "kind": "Authorino",
            "metadata": {"name": name, "namespace": openshift.project},
            "spec": {
                "clusterWide": cluster_wide,
                "logLevel": log_level,
                "listener": {"tls": {"enabled": False}},
                "oidcServer": {"tls": {"enabled": False}},
            },
        }
        if image:
            model["spec"]["image"] = image

        if label_selectors:
            model["spec"]["authConfigLabelSelectors"] = ",".join(label_selectors)

        if listener_certificate_secret:
            model["spec"]["listener"]["tls"] = {"enabled": True, "certSecretRef": {"name": listener_certificate_secret}}

        with openshift.context:
            return cls(model)

    def wait_for_ready(self):
        """Waits until Authorino CR reports ready status"""
        with timeout(90):
            success, _, _ = self.self_selector().until_all(
                success_func=lambda obj: len(obj.model.status.conditions) > 0
                and all(x.status == "True" for x in obj.model.status.conditions)
            )
            assert success, "Authorino did got get ready in time"
            self.refresh()

    @property
    def deployment(self):
        """Returns Deployment object for this Authorino"""
        with self.context:
            return selector(f"deployment/{self.name()}").object()

    @property
    def metrics_service(self):
        """Returns Authorino metrics service APIObject"""
        with self.context:
            return selector(f"service/{self.name()}-controller-metrics").object()

    @property
    def authorization_url(self):
        """Return service endpoint for authorization"""
        return f"{self.name()}-authorino-authorization.{self.namespace()}.svc.cluster.local"

    @property
    def oidc_url(self):
        """Return authorino oidc endpoint"""
        return f"{self.name()}-authorino-oidc.{self.namespace()}.svc.cluster.local"


class PreexistingAuthorino(Authorino):
    """Authorino which is already deployed prior to the testrun"""

    def __init__(self, authorization_url, oidc_url, metrics_service) -> None:
        super().__init__()
        self._authorization_url = authorization_url
        self._oidc_url = oidc_url
        self._metrics_service = metrics_service

    def wait_for_ready(self):
        return True

    @property
    def metrics_service(self):
        return self._metrics_service

    @property
    def authorization_url(self):
        return self._authorization_url

    @property
    def oidc_url(self):
        return self._oidc_url

    def commit(self):
        return

    def delete(self):
        return
