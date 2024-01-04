"""Service related objects"""
from testsuite.openshift import OpenShiftObject


class Service(OpenShiftObject):
    """Kubernetes Service object"""

    @classmethod
    def create_instance(
        cls,
        openshift,
        name,
        selector: dict[str, str],
        ports: list[dict[str, str]],
        labels: dict[str, str] = None,
    ):
        """Creates new Service"""
        model: dict = {
            "kind": "Service",
            "apiVersion": "v1",
            "metadata": {
                "name": name,
                "labels": labels,
            },
            "spec": {
                "ports": ports,
                "selector": selector,
            },
        }
        return cls(model, context=openshift.context)

    def get_port(self, name):
        """Returns port definition for a port with said name"""
        for port in self.model.spec.ports:
            if port["name"] == name:
                return port
        raise KeyError(f"No port with name {name} exists")
