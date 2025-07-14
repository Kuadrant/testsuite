from testsuite.backend import Backend
from testsuite.kubernetes import Selector
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kubernetes.deployment import Deployment
from testsuite.kubernetes.service import Service, ServicePort

class LlmSim(Backend):
    """LlmSim deployed in Kubernetes as Backend"""

    def __init__(self, cluster: KubernetesClient, name, label, image, replicas=1) -> None:
        super().__init__(cluster, name, label)
        self.replicas = replicas
        self.image = image

    def commit(self):
        match_labels = {"app": self.label, "deployment": self.name}
        self.deployment = Deployment.create_instance(
            self.cluster,
            self.name,
            container_name="llm-sim",
            image=self.image,
            ports={"api": 8080},
            selector=Selector(matchLabels=match_labels),
            labels={"app": self.label},
            command_args=["--model", "meta-llama/Llama-3.1-8B-Instruct", "--port", "8080"],
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