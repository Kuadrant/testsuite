"""General exposers, not tied to Envoy or Gateway API"""

from testsuite.certificates import Certificate
from testsuite.gateway import Exposer, Gateway, Hostname
from testsuite.httpx import KuadrantClient
from testsuite.openshift.route import OpenshiftRoute


class OpenShiftExposer(Exposer):
    """Exposes hostnames through OpenShift Route objects"""

    def __init__(self, openshift) -> None:
        super().__init__(openshift)
        self.routes: list[OpenshiftRoute] = []

    @property
    def base_domain(self) -> str:
        return self.openshift.apps_url

    def expose_hostname(self, name, gateway: Gateway) -> Hostname:
        tls = False
        termination = "edge"
        if self.passthrough:
            tls = True
            termination = "passthrough"
        route = OpenshiftRoute.create_instance(
            gateway.openshift, name, gateway.service_name, "api", tls=tls, termination=termination
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
        return KuadrantClient(base_url=f"{protocol}://{self.ip_getter()}", **kwargs)

    @property
    def hostname(self):
        return self._hostname


class KindExposer(Exposer):
    """Exposer using loadbalancer service for Gateway"""

    def expose_hostname(self, name, gateway: Gateway) -> Hostname:
        return StaticLocalHostname(
            f"{name}.{self.base_domain}", gateway.external_ip, gateway.get_tls_cert(), force_https=self.passthrough
        )

    @property
    def base_domain(self) -> str:
        return "test.com"

    def commit(self):
        pass

    def delete(self):
        pass
