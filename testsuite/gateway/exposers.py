from testsuite.gateway import Exposer, Gateway, Hostname
from testsuite.lifecycle import LifecycleObject
from testsuite.openshift.route import OpenshiftRoute


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
