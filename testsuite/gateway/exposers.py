"""General exposers, not tied to Envoy or Gateway API"""

from testsuite.config import settings
from testsuite.gateway import Exposer, Gateway, Hostname
from testsuite.httpx import KuadrantClient, ForceSNIClient
from testsuite.kubernetes.openshift.route import OpenshiftRoute
from testsuite.kubernetes.service import Service, ServicePort


class OpenShiftExposer(Exposer):
    """Exposes hostnames through OpenShift Route objects"""

    def __init__(self, cluster) -> None:
        super().__init__(cluster)
        self.routes: list[OpenshiftRoute] = []

    @property
    def base_domain(self) -> str:
        return self.cluster.apps_url

    def expose_hostname(self, name, exposable) -> Hostname:
        tls = False
        termination = "edge"
        if self.passthrough:
            tls = True
            termination = "passthrough"
        route = OpenshiftRoute.create_instance(
            exposable.cluster, name, exposable.service_name, "api", tls=tls, termination=termination
        )
        route.verify = self.verify
        self.routes.append(route)
        route.commit()
        return route

    def commit(self):
        return

    def delete(self):
        for route in self.routes:
            route.delete()
        self.routes = []


class StaticLocalHostname(Hostname):
    """Static local IP hostname"""

    def __init__(self, hostname, ip_getter, verify_getter=None, force_https: bool = False):
        self._hostname = hostname
        self.ip_getter = ip_getter
        self.verify_getter = verify_getter
        self.force_https = force_https

    def client(self, **kwargs) -> KuadrantClient:
        headers = kwargs.setdefault("headers", {})
        headers["Host"] = self.hostname
        ip = self.ip_getter()
        verify = self.verify_getter() if self.verify_getter else None
        protocol = "http"
        if verify or self.force_https:
            ip = ip.replace(":80", ":443")
            protocol = "https"
            kwargs.setdefault("verify", verify)
        return ForceSNIClient(base_url=f"{protocol}://{ip}", sni_hostname=self.hostname, **kwargs)

    @property
    def hostname(self):
        return self._hostname


class LoadBalancerServiceExposer(Exposer):
    """Exposer using Load Balancer service for Gateway"""

    def expose_hostname(self, name, exposable) -> Hostname:
        hostname = f"{name}.{self.base_domain}"
        return StaticLocalHostname(
            hostname, exposable.external_ip, lambda: exposable.get_tls_cert(hostname), force_https=self.passthrough
        )

    def expose_backend(self, name, backend) -> Hostname:
        """Creates a LoadBalancer service for direct external access to the backend"""
        admin_svc_name = f"{backend.service_name}-admin"
        admin_service = Service.create_instance(
            backend.cluster,
            admin_svc_name,
            selector=backend.match_labels,
            ports=[ServicePort(name="admin", port=8080, targetPort="api")],
            labels={"app": backend.label},
            service_type="LoadBalancer",
        )
        admin_service.commit()
        admin_service.wait_for_ready(slow_loadbalancers=settings["control_plane"]["slow_loadbalancers"])
        backend._admin_service = admin_service  # pylint: disable=protected-access
        return StaticLocalHostname(
            admin_svc_name,
            lambda: f"{admin_service.refresh().external_ip}:8080",
        )

    @property
    def base_domain(self) -> str:
        return "test.com"

    def commit(self):
        pass

    def delete(self):
        pass
