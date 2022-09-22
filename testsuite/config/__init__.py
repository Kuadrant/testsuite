"""Module which initializes Dynaconf"""

from dynaconf import Dynaconf, Validator

from testsuite.config.tools import fetch_route, fetch_secret


# pylint: disable=too-few-public-methods
class DefaultValueValidator(Validator):
    """Validator which will run default function only when the original value is missing"""

    def __init__(self, name, default, **kwargs) -> None:
        super().__init__(name, ne=None,
                         messages={
                             "operations": ("{name} must {operation} {op_value} but it is {value} in env {env}. "
                                            "You might be missing tools on the cluster.")
                         },
                         default=default,
                         when=Validator(name, must_exist=False),
                         **kwargs)


settings = Dynaconf(
    environments=True,
    lowercase_read=True,
    load_dotenv=True,
    settings_files=["config/settings.yaml", "config/secrets.yaml"],
    envvar_prefix="KUADRANT",
    merge_enabled=True,
    validators=[
        Validator("authorino.deploy", eq=True) | Validator("authorino.url", must_exist=True),
        DefaultValueValidator("rhsso.url", must_exist=True, default=fetch_route("no-ssl-sso")),
        DefaultValueValidator("rhsso.password",
                              must_exist=True, default=fetch_secret("credential-sso", "ADMIN_PASSWORD")),
        DefaultValueValidator("mockserver.url", must_exist=True, default=fetch_route("no-ssl-mockserver")),
    ],
    loaders=["testsuite.config.openshift_loader", "dynaconf.loaders.env_loader"]
)
