"""General exposers, not tied to Envoy or Gateway API"""

from testsuite.certificates import Certificate
from testsuite.gateway import Exposer, Gateway, Hostname
from testsuite.httpx import KuadrantClient, ForceSNIClient
from testsuite.kubernetes.openshift.route import OpenshiftRoute


class OpenShiftExposer(Exposer):
    """Exposes hostnames through OpenShift Route objects"""

    def __init__(self, cluster) -> None:
        super().__init__(cluster)
        self.routes: list[OpenshiftRoute] = []

    @property
    def base_domain(self) -> str:
        return self.cluster.apps_url

    def expose_hostname(self, name, gateway: Gateway) -> Hostname:
        tls = False
        termination = "edge"
        if self.passthrough:
            tls = True
            termination = "passthrough"
        route = OpenshiftRoute.create_instance(
            gateway.cluster, name, gateway.service_name, "api", tls=tls, termination=termination
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

    def expose_metrics(self, gateway):
        """
        Expose metrics via ClusterIP Service + Route.

        Returns:
            str: The metrics endpoint URL
        """
        from testsuite.kubernetes.service import Service, ServicePort

        # Create ClusterIP service
        metrics_service = Service.create_instance(
            gateway.cluster,
            gateway.metrics_service_name,
            selector={"gateway.networking.k8s.io/gateway-name": gateway.name()},
            ports=[ServicePort(name="metrics", port=15020, targetPort=15020)],
            labels=gateway.model.metadata.get("labels", {}),
            service_type="ClusterIP",
        )
        metrics_service.commit()

        # Create Route to expose the service
        metrics_route = OpenshiftRoute.create_instance(
            gateway.cluster,
            gateway.metrics_service_name,
            gateway.metrics_service_name,
            target_port="metrics",
            tls=False
        )
        metrics_route.commit()

        # Track for cleanup
        self.routes.append(metrics_route)

        return f"http://{metrics_route.hostname}/stats/prometheus"


class StaticLocalHostname(Hostname):
    """Static local IP hostname"""

    def __init__(self, hostname, ip_getter, verify: Certificate = None, force_https: bool = False):
        self._hostname = hostname
        self.verify = verify
        self.ip_getter = ip_getter
        self.force_https = force_https

    def client(self, **kwargs) -> KuadrantClient:
        headers = kwargs.setdefault("headers", {})
        headers["Host"] = self.hostname
        protocol = "http"
        if self.verify or self.force_https:
            protocol = "https"
            kwargs.setdefault("verify", self.verify)
        return ForceSNIClient(base_url=f"{protocol}://{self.ip_getter()}", sni_hostname=self.hostname, **kwargs)

    @property
    def hostname(self):
        return self._hostname


class LoadBalancerServiceExposer(Exposer):
    """Exposer using Load Balancer service for Gateway"""

    def expose_hostname(self, name, gateway: Gateway) -> Hostname:
        hostname = f"{name}.{self.base_domain}"
        return StaticLocalHostname(
            hostname, gateway.external_ip, gateway.get_tls_cert(hostname), force_https=self.passthrough
        )

    @property
    def base_domain(self) -> str:
        return "test.com"

    def commit(self):
        pass

    def delete(self):
        pass

    def expose_metrics(self, gateway):
        """
        Expose metrics via gateway's external IP directly (no separate service needed).

        Returns:
            str: The metrics endpoint URL (will be available after gateway.wait_for_ready())
        """
        # For LoadBalancer exposer (Kind/local), use the gateway's external IP directly
        # The gateway already exposes port 15020 for metrics
        # Return a lambda that gets the IP when actually needed (after gateway is ready)
        return lambda: f"http://{gateway.external_ip().split(':')[0]}:15020/stats/prometheus"
