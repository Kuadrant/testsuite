"""Module which initializes Dynaconf"""
from dynaconf import Dynaconf, Validator

from testsuite.config.tools import fetch_route, fetch_from_secret

settings = Dynaconf(
    environments=True,
    lowercase_read=True,
    load_dotenv=True,
    settings_files=["config/settings.yaml", "config/secrets.yaml"],
    envvar_prefix="KUADRANT",
    merge_enabled=True,
    validators=[
        Validator("authorino.deploy", eq=True) | Validator("authorino.url", must_exist=True),
        Validator("rhsso.url", must_exist=True),
        Validator("rhsso.password", must_exist=True),
    ],
    loaders=["testsuite.config.openshift_loader", "testsuite.config.tools", "dynaconf.loaders.env_loader"]
)
