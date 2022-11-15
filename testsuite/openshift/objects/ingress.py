"""Kubernetes Ingress object"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import openshift as oc

from testsuite.objects import LifecycleObject
from testsuite.openshift.objects import OpenShiftObject

if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from testsuite.openshift.client import OpenShiftClient


class Ingress(OpenShiftObject, LifecycleObject):
    """Represents Kubernetes Ingress object"""

    @classmethod
    def create_instance(cls, openshift: 'OpenShiftClient', name, rules: Optional[List[Dict[str, Any]]] = None,
                        tls: Optional[List[Dict[str, Any]]] = None):
        """Creates base instance"""
        if rules is None:
            rules = []

        if tls is None:
            tls = []

        model: Dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": name,
                "namespace": openshift.project
            },
            "spec": {
                "rules": rules,
                "tls": tls
            }
        }

        with openshift.context:
            return cls(model)

    @classmethod
    def create_service_ingress(cls, openshift: 'OpenShiftClient', name, service_name, port_number=80, path="/",
                               path_type="Prefix", host=None):
        """
        Creates Ingress instance for service without tls configured
        """
        rule = {
            "http": {
                "paths": [
                    {
                        "backend": {
                            "service": {
                                "name": service_name,
                                "port": {
                                    "number": port_number
                                }
                            }
                        },
                        "path": path,
                        "pathType": path_type
                    },
                ]
            }
        }

        if host is not None:
            rule["host"] = host

        return cls.create_instance(openshift, name, rules=[rule])

    @property
    def rules(self):
        """Returns rules defined in the ingress"""
        return self.model.spec.rules

    @property
    def host(self):
        """Returns host of the ingress"""
        return self.model.metadata.annotations["kuadrant.dev/host.generated"]

    def wait(self, timeout=360):
        """
        Waits until the Ingress is ready,
        temporarily it just checks for certificate as that is almost certainly created afterwards
        """
        return self.wait_for_certificate(timeout=timeout)

    def wait_for_certificate(self, tolerate_failures: int = 5, timeout=360):
        """Waits until all rules within the ingress have host fields filled"""
        def _certificate_ready(obj):
            return obj.model.metadata.annotations["kuadrant.dev/certificate-status"] == "ready"

        with oc.timeout(timeout):
            success, _, _ = self.self_selector().until_all(success_func=_certificate_ready,
                                                           tolerate_failures=tolerate_failures)

        return success
