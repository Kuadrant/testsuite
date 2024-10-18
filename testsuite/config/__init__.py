"""Module which initializes Dynaconf"""

from dynaconf import Dynaconf, Validator

from testsuite.utils import hostname_to_ip
from testsuite.config.tools import fetch_route, fetch_service, fetch_secret, fetch_service_ip


# pylint: disable=too-few-public-methods
class DefaultValueValidator(Validator):
    """Validator which will run default function only when the original value is missing"""

    def __init__(self, name, default, **kwargs) -> None:
        super().__init__(
            name,
            ne=None,
            messages={
                "operations": (
                    "{name} must {operation} {op_value} but it is {value} in env {env}. "
                    "You might be missing tools on the cluster."
                )
            },
            default=default,
            when=Validator(name, must_exist=False) | Validator(name, eq=None),
            **kwargs
        )


settings = Dynaconf(
    environments=True,
    lowercase_read=True,
    load_dotenv=True,
    settings_files=["config/settings.yaml", "config/secrets.yaml"],
    envvar_prefix="KUADRANT",
    merge_enabled=True,
    validators=[
        Validator("service_protection.authorino.deploy", must_exist=True, eq=True)
        | (
            Validator("service_protection.authorino.auth_url", must_exist=True)
            & Validator("service_protection.authorino.oidc_url", must_exist=True)
        ),
        DefaultValueValidator("tracing.backend", default="jaeger", is_in=["jaeger", "tempo"]),
        DefaultValueValidator(
            "tracing.collector_url", default=fetch_service("jaeger-collector", protocol="rpc", port=4317)
        ),
        DefaultValueValidator("tracing.query_url", default=fetch_service_ip("jaeger-query", force_http=True, port=80)),
        Validator(
            "default_exposer",
            # If exposer was successfully converted, it will no longer be a string"""
            condition=lambda exposer: not isinstance(exposer, str),
            must_exist=True,
            messages={"condition": "{value} is not valid exposer"},
        ),
        Validator("control_plane.provider_secret", must_exist=True, ne=None),
        (
            Validator("control_plane.issuer.name", must_exist=True, ne=None)
            & Validator("control_plane.issuer.kind", must_exist=True, is_in={"Issuer", "ClusterIssuer"})
        ),
        (
            Validator("letsencrypt.issuer.name", must_exist=True, ne=None)
            & Validator("letsencrypt.issuer.kind", must_exist=True, is_in={"Issuer", "ClusterIssuer"})
        ),
        (
            Validator("dns.dns_server.address", must_exist=True, ne=None, cast=hostname_to_ip)
            & Validator("dns.dns_server.geo_code", must_exist=True, ne=None)
            & Validator("dns.dns_server2.address", must_exist=True, ne=None, cast=hostname_to_ip)
            & Validator("dns.dns_server2.geo_code", must_exist=True, ne=None)
        ),
        DefaultValueValidator("keycloak.url", default=fetch_service_ip("keycloak", force_http=True, port=8080)),
        DefaultValueValidator("keycloak.password", default=fetch_secret("keycloak-initial-admin", "password")),
        DefaultValueValidator("mockserver.url", default=fetch_service_ip("mockserver", force_http=True, port=1080)),
    ],
    validate_only=["authorino", "kuadrant", "default_exposer", "control_plane"],
    loaders=["dynaconf.loaders.env_loader", "testsuite.config.openshift_loader", "testsuite.config.exposer"],
)
