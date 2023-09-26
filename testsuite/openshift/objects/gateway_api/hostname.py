"""Module containing implementation for Hostname related classes of Gateway API"""
from httpx import Client

from testsuite.certificates import Certificate
from testsuite.httpx import KuadrantClient
from testsuite.objects import LifecycleObject
from testsuite.objects.gateway import Gateway
from testsuite.objects.hostname import Exposer, Hostname
from testsuite.openshift.objects.route import OpenshiftRoute


class OpenShiftExposer(Exposer, LifecycleObject):
    """Exposes hostnames through OpenShift Route objects"""

    def __init__(self, passthrough=False) -> None:
        super().__init__()
        self.routes: list[OpenshiftRoute] = []
        self.passthrough = passthrough

    def expose_hostname(self, name, gateway: Gateway) -> Hostname:
        tls = False
        termination = "edge"
        if self.passthrough:
            tls = True
            termination = "passthrough"
        route = OpenshiftRoute.create_instance(
            gateway.openshift, name, gateway.service_name, "api", tls=tls, termination=termination
        )
        self.routes.append(route)
        route.commit()
        return route

    def commit(self):
        return

    def delete(self):
        for route in self.routes:
            route.delete()
        self.routes = []


class StaticHostname(Hostname):
    """Already exposed hostname object"""

    def __init__(self, hostname, tls_cert: Certificate = None):
        super().__init__()
        self._hostname = hostname
        self.tls_cert = tls_cert

    def client(self, **kwargs) -> Client:
        protocol = "http"
        if self.tls_cert:
            protocol = "https"
            kwargs.setdefault("verify", self.tls_cert)
        return KuadrantClient(base_url=f"{protocol}://{self.hostname}", **kwargs)

    @property
    def hostname(self):
        return self._hostname


class DNSPolicyExposer(Exposer):
    """Exposing is done as part of DNSPolicy, so no work needs to be done here"""

    def __init__(self, base_domain, tls_cert: Certificate = None):
        super().__init__()
        self.base_domain = base_domain
        self.tls_cert = tls_cert

    def expose_hostname(self, name, gateway: Gateway) -> Hostname:
        return StaticHostname(f"{name}.{self.base_domain}", gateway.get_tls_cert())
