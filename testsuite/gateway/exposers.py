"""General exposers, not tied to Envoy or Gateway API"""

import yaml
from openshift_client import OpenShiftPythonException, selector

from testsuite.gateway import Exposer, Gateway, Hostname
from testsuite.httpx import KuadrantClient, ForceSNIClient
from testsuite.kubernetes.config_map import ConfigMap
from testsuite.kubernetes.openshift.route import OpenshiftRoute
from testsuite.kubernetes.service import Service


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

    def prometheus_client(self):
        """Discover Prometheus via thanos-querier route in openshift-monitoring"""
        try:
            openshift_monitoring = self.cluster.change_project("openshift-monitoring")

            with openshift_monitoring.context:
                cm = selector("cm/cluster-monitoring-config").object(cls=ConfigMap)
                if not yaml.safe_load(cm["config.yaml"])["enableUserWorkload"]:
                    return None

            routes = openshift_monitoring.get_routes_for_service("thanos-querier")
            if not routes:
                return None
            url = ("https://" if "tls" in routes[0].model.spec else "http://") + routes[0].model.spec.host
            return KuadrantClient(headers={"Authorization": f"Bearer {self.cluster.token}"}, base_url=url, verify=False)
        except (OpenShiftPythonException, KeyError, AttributeError, yaml.YAMLError):
            return None

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

    PROMETHEUS_SERVICE = "prometheus-kube-prometheus-prometheus"
    PROMETHEUS_NAMESPACE = "monitoring"

    def expose_hostname(self, name, gateway: Gateway) -> Hostname:
        hostname = f"{name}.{self.base_domain}"
        return StaticLocalHostname(
            hostname, gateway.external_ip, lambda: gateway.get_tls_cert(hostname), force_https=self.passthrough
        )

    @property
    def base_domain(self) -> str:
        return "test.com"

    def prometheus_client(self):
        """Discover Prometheus via LoadBalancer service in monitoring namespace"""
        try:
            monitoring = self.cluster.change_project(self.PROMETHEUS_NAMESPACE)
            with monitoring.context:
                svc = selector(f"service/{self.PROMETHEUS_SERVICE}").object(cls=Service)
                port = svc.model.spec.ports[0].port
                return KuadrantClient(base_url=f"http://{svc.external_ip}:{port}", verify=False)
        except (OpenShiftPythonException, KeyError, AttributeError):
            return None

    def commit(self):
        pass

    def delete(self):
        pass
