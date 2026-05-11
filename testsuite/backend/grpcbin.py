"""Grpcbin implementation of Backend"""

from testsuite.backend import Backend
from testsuite.kubernetes import Selector
from testsuite.kubernetes.certificate import Certificate
from testsuite.kubernetes.client import KubernetesClient
from testsuite.kubernetes.deployment import Deployment, SecretVolume, VolumeMount
from testsuite.kubernetes.service import Service, ServicePort


class Grpcbin(Backend):
    """Grpcbin deployed in Kubernetes as Backend"""

    GRPC_PORT = 9000
    GRPC_TLS_PORT = 9001

    def __init__(self, cluster: KubernetesClient, name, label, image, *, cluster_issuer) -> None:
        super().__init__(cluster, name, label)
        self.image = image
        self.cluster_issuer = cluster_issuer
        self.certificate = None
        self.deployment = None
        self.service = None

    @property
    def reference(self):
        return {
            "group": "",
            "kind": "Service",
            "port": self.GRPC_PORT,
            "name": self.name,
            "namespace": self.cluster.project,
        }

    def commit(self):
        secret_name = f"{self.name}-tls"
        dns_names = [
            self.name,
            f"{self.name}.{self.cluster.project}.svc",
            f"{self.name}.{self.cluster.project}.svc.cluster.local",
        ]
        self.certificate = Certificate.create_instance(
            self.cluster, f"{self.name}-cert", secret_name, self.cluster_issuer, dns_names
        )
        self.certificate.commit()
        self.certificate.wait_for_ready()

        match_labels = {"app": self.label, "deployment": self.name}
        self.deployment = Deployment.create_instance(
            self.cluster,
            self.name,
            container_name="grpcbin",
            image=self.image,
            ports={"grpc": self.GRPC_PORT, "grpc-tls": self.GRPC_TLS_PORT},
            selector=Selector(matchLabels=match_labels),
            labels={"app": self.label},
            command_args=["-tls-cert=/certs/tls.crt", "-tls-key=/certs/tls.key"],
            volumes=[SecretVolume(secret_name=secret_name, name="tls")],
            volume_mounts=[VolumeMount(mountPath="/certs", name="tls", readOnly=True)],
        )
        self.deployment.commit()
        self.deployment.wait_for_ready()

        self.service = Service.create_instance(
            self.cluster,
            self.name,
            selector=match_labels,
            ports=[
                ServicePort(name="grpc", port=self.GRPC_PORT, targetPort="grpc"),
                ServicePort(name="grpc-tls", port=self.GRPC_TLS_PORT, targetPort="grpc-tls"),
            ],
            labels={"app": self.label},
        )
        self.service.commit()

    def delete(self):
        with self.cluster.context:
            if self.certificate:
                self.certificate.delete()
                self.certificate = None
        super().delete()
