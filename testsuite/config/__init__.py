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
        DefaultValueValidator("tracing.query_url", default=fetch_service_ip("jaeger-query", protocol="http", port=80)),
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
        Validator("dns.coredns_zone", must_exist=True, ne=None),
        (
            Validator("dns.dns_server.address", must_exist=True, ne=None, cast=hostname_to_ip)
            & Validator("dns.dns_server.geo_code", must_exist=True, ne=None)
            & Validator("dns.dns_server2.address", must_exist=True, ne=None, cast=hostname_to_ip)
            & Validator("dns.dns_server2.geo_code", must_exist=True, ne=None)
        ),
        Validator("dns.default_geo_server", must_exist=True, ne=None, cast=hostname_to_ip),
        DefaultValueValidator("keycloak.url", default=fetch_service_ip("keycloak", protocol="http", port=8080)),
        DefaultValueValidator("keycloak.password", default=fetch_secret("credential-sso", "ADMIN_PASSWORD")),
        DefaultValueValidator("mockserver.url", default=fetch_service_ip("mockserver", protocol="http", port=1080)),
        DefaultValueValidator("redis.url", default=fetch_service_ip("redis", protocol="redis", port=6379)),
        DefaultValueValidator("dragonfly.url", default=fetch_service_ip("dragonfly", protocol="redis", port=6379)),
        DefaultValueValidator("valkey.url", default=fetch_service_ip("valkey", protocol="redis", port=6379)),
        DefaultValueValidator("mockserver.url", default=fetch_service_ip("mockserver", protocol="http", port=1080)),
        DefaultValueValidator(
            "custom_metrics_apiserver.url",
            default=fetch_service_ip("custom-metrics-apiserver", protocol="http", port=8080),
        ),
        DefaultValueValidator("spicedb.url", default=fetch_service_ip("spicedb", port=50051)),
        DefaultValueValidator("spicedb.password", default=fetch_secret("spicedb-key", "SPICEDB_GRPC_PRESHARED_KEY")),
    ],
    validate_only=["authorino", "kuadrant", "default_exposer", "control_plane"],
    loaders=["dynaconf.loaders.env_loader", "testsuite.config.openshift_loader", "testsuite.config.exposer"],
)
