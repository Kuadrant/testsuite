"""Testsuite configuration"""
from dynaconf import Dynaconf, Validator

settings = Dynaconf(
    environments=True,
    lowercase_read=True,
    load_dotenv=True,
    settings_files=["config/settings.yaml", "config/secrets.yaml"],
    envvar_prefix="KUADRANT",
    merge_enabled=True,
    validators=[
        Validator("authorino.deploy", eq=True) | Validator("authorino.url", must_exist=True)
    ]
)
