"""Mockserver implementation as Backend"""

from testsuite.config import settings
from testsuite.backend import Backend
from testsuite.kubernetes import Selector
from testsuite.kubernetes.deployment import Deployment, ContainerResources
from testsuite.kubernetes.service import Service, ServicePort


class MockserverBackend(Backend):
    """Mockserver deployed as backend in Kubernetes"""

    def commit(self):
        match_labels = {"app": self.label, "deployment": self.name}
        self.deployment = Deployment.create_instance(
            self.cluster,
            self.name,
            container_name="mockserver",
            image=settings["mockserver"]["image"],
            ports={"api": 1080},
            selector=Selector(matchLabels=match_labels),
            labels={"app": self.label},
            resources=ContainerResources(limits_memory="2G"),
            lifecycle={"postStart": {"exec": {"command": ["/bin/sh", "init-mockserver"]}}},
        )
        self.deployment.commit()

        self.service = Service.create_instance(
            self.cluster,
            self.name,
            selector=match_labels,
            ports=[ServicePort(name="1080-tcp", port=8080, targetPort="api")],
            labels={"app": self.label},
            service_type="LoadBalancer",
        )
        self.service.commit()

    def wait_for_ready(self, timeout=60 * 5):
        """Waits until Deployment and Service is marked as ready"""
        self.deployment.wait_for_ready(timeout)
        self.service.wait_for_ready(timeout, settings["control_plane"]["slow_loadbalancers"])
