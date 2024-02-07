"""Module which initializes Dynaconf"""

from dynaconf import Dynaconf, Validator

from testsuite.config.tools import fetch_route, fetch_secret


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
        DefaultValueValidator("rhsso.url", default=fetch_route("no-ssl-sso")),
        DefaultValueValidator("rhsso.password", default=fetch_secret("credential-sso", "ADMIN_PASSWORD")),
        DefaultValueValidator("mockserver.url", default=fetch_route("mockserver", force_http=True)),
    ],
    validate_only=["authorino", "kuadrant"],
    loaders=["dynaconf.loaders.env_loader", "testsuite.config.openshift_loader"],
)
