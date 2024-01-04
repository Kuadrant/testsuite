"""Deployment related objects"""
from testsuite.openshift import OpenShiftObject, Selector
from testsuite.utils import asdict


class Deployment(OpenShiftObject):
    """Kubernetes Deployment object"""

    @classmethod
    def create_instance(
        cls, openshift, name, container_name, image, ports: dict[str, int], selector: Selector, labels: dict[str, str]
    ):
        """
        Creates new instance of Deployment
        Supports only single container Deployments everything else should be edited directly
        """
        model: dict = {
            "kind": "Deployment",
            "apiVersion": "apps/v1",
            "metadata": {
                "name": name,
                "labels": labels,
            },
            "spec": {
                "selector": asdict(selector),
                "template": {
                    "metadata": {"labels": {"deployment": name, **labels}},
                    "spec": {
                        "containers": [
                            {
                                "image": image,
                                "name": container_name,
                                "imagePullPolicy": "IfNotPresent",
                                "ports": [{"name": name, "containerPort": port} for name, port in ports.items()],
                            }
                        ]
                    },
                },
            },
        }

        return cls(model, context=openshift.context)
