"""Service related objects"""

from dataclasses import dataclass, asdict

from testsuite.openshift import OpenShiftObject


@dataclass
class ServicePort:
    """Kubernetes Service Port object"""

    name: str
    port: int
    targetPort: int | str  # pylint: disable=invalid-name


class Service(OpenShiftObject):
    """Kubernetes Service object"""

    @classmethod
    def create_instance(
        cls,
        openshift,
        name,
        selector: dict[str, str],
        ports: list[ServicePort],
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
                "ports": [asdict(port) for port in ports],
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
