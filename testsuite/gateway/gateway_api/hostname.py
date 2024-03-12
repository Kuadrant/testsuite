"""Module containing implementation for Hostname related classes of Gateway API"""

from functools import cached_property

from httpx import Client
from openshift_client import selector

from testsuite.certificates import Certificate
from testsuite.config import settings
from testsuite.httpx import KuadrantClient
from testsuite.gateway import Gateway, Hostname, Exposer
from testsuite.utils import generate_tail


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

    @cached_property
    def base_domain(self) -> str:
        mz_name = settings["control_plane"]["managedzone"]
        zone = selector(f"managedzone/{mz_name}", static_context=self.openshift.context).object()
        return f'{generate_tail(5)}.{zone.model["spec"]["domainName"]}'

    def expose_hostname(self, name, gateway: Gateway) -> Hostname:
        return StaticHostname(
            f"{name}.{self.base_domain}", gateway.get_tls_cert() if self.verify is None else self.verify
        )

    def commit(self):
        pass

    def delete(self):
        pass
