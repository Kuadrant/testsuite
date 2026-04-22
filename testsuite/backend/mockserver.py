"""Mockserver implementation as Backend"""

from testsuite.config import settings
from testsuite.backend import Backend
from testsuite.kubernetes import Selector
from testsuite.kubernetes.config_map import ConfigMap
from testsuite.kubernetes.deployment import Deployment, ContainerResources, ConfigMapVolume, VolumeMount
from testsuite.kubernetes.service import Service, ServicePort

INIT_JSON_MOUNT = "/config/mockserver"


class MockserverBackendConfig:
    """Initial configuration for MockServer loaded at startup via ConfigMap"""

    def __init__(self, cluster, name, label, data: dict[str, str]):
        self.cluster = cluster
        self.name = name
        self.label = label
        self.data = data
        self.config_map = None

    def commit(self):
        """Creates and commits the ConfigMap"""
        self.config_map = ConfigMap.create_instance(
            self.cluster,
            self.name,
            data=self.data,
            labels={"app": self.label},
        )
        self.config_map.commit()

    @property
    def volumes(self):
        """Volumes to mount into the MockServer container"""
        return [ConfigMapVolume(
            config_map_name=self.config_map.name(),
            items={k: k for k in self.data},
            name="init-config",
        )]

    @property
    def volume_mounts(self):
        """Volume mounts for the MockServer container"""
        return [VolumeMount(mountPath=INIT_JSON_MOUNT, name="init-config", readOnly=True)]

    @property
    def env(self):
        """Environment variables for the MockServer container"""
        init_file = next(iter(self.data))
        return {"MOCKSERVER_INITIALIZATION_JSON_PATH": f"{INIT_JSON_MOUNT}/{init_file}"}

    def delete(self):
        """Deletes the ConfigMap"""
        if self.config_map:
            self.config_map.delete(ignore_not_found=True)
            self.config_map = None


class MockserverBackend(Backend):
    """Mockserver deployed as backend in Kubernetes"""

    def __init__(self, cluster, name, label, service_type="LoadBalancer", config=None):
        super().__init__(cluster, name, label)
        self.service_type = service_type
        self.config = config

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
            volumes=self.config.volumes if self.config else None,
            volume_mounts=self.config.volume_mounts if self.config else None,
            env=self.config.env if self.config else None,
        )
        self.deployment.commit()

        self.service = Service.create_instance(
            self.cluster,
            self.name,
            selector=match_labels,
            ports=[ServicePort(name="http", port=8080, targetPort="api")],
            labels={"app": self.label},
            service_type=self.service_type,
        )
        self.service.commit()

    def delete(self):
        if self.config:
            with self.cluster.context:
                self.config.delete()
        super().delete()

    def wait_for_ready(self, timeout=60 * 5):
        """Waits until Deployment and Service is marked as ready"""
        self.deployment.wait_for_ready(timeout)
        self.service.wait_for_ready(timeout, settings["control_plane"]["slow_loadbalancers"])
