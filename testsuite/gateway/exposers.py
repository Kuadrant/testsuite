"""General exposers, not tied to Envoy or Gateway API"""

from testsuite.gateway import Exposer, Gateway, Hostname
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
