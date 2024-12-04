"""Httpbin implementation of Backend"""

from testsuite.backend import Backend
from testsuite.kubernetes import Selector
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kubernetes.deployment import Deployment
from testsuite.kubernetes.service import Service, ServicePort


class Httpbin(Backend):
    """Httpbin deployed in Kubernetes as Backend"""

    def __init__(self, cluster: KubernetesClient, name, label, image, replicas=1) -> None:
        super().__init__(cluster, name, label)
        self.replicas = replicas
        self.image = image

    def commit(self):
        match_labels = {"app": self.label, "deployment": self.name}
        self.deployment = Deployment.create_instance(
            self.cluster,
            self.name,
            container_name="httpbin",
            image=self.image,
            ports={"api": 8080},
            selector=Selector(matchLabels=match_labels),
            labels={"app": self.label},
        )
        self.deployment.commit()
        self.deployment.wait_for_ready()

        self.service = Service.create_instance(
            self.cluster,
            self.name,
            selector=match_labels,
            ports=[ServicePort(name="http", port=8080, targetPort="api")],
        )
        self.service.commit()
