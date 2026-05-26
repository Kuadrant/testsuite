"""LlmSim implementation for backend"""

from testsuite.backend import Backend
from testsuite.kubernetes import Selector
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kubernetes.deployment import Deployment
from testsuite.kubernetes.service import Service, ServicePort
from testsuite.utils.constants import HTTP_API_PORT


class LlmSim(Backend):
    """LlmSim deployed in Kubernetes as Backend"""

    def __init__(self, cluster: KubernetesClient, name, model, label, image, replicas=1) -> None:
        super().__init__(cluster, name, label)
        self.model = model
        self.replicas = replicas
        self.image = image

    def commit(self):
        match_labels = {"app": self.label, "deployment": self.name}
        self.deployment = Deployment.create_instance(
            self.cluster,
            self.name,
            container_name="llm-sim",
            image=self.image,
            ports={"api": HTTP_API_PORT},
            selector=Selector(matchLabels=match_labels),
            labels={"app": self.label},
            command_args=["--model", self.model, "--port", str(HTTP_API_PORT)],
        )
        self.deployment.commit()
        self.deployment.wait_for_ready()

        self.service = Service.create_instance(
            self.cluster,
            self.name,
            selector=match_labels,
            ports=[ServicePort(name="http", port=HTTP_API_PORT, targetPort="api")],
        )
        self.service.commit()
