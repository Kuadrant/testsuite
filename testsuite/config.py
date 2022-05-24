"""Testsuite configuration"""
from dynaconf import Dynaconf

settings = Dynaconf(
    environments=True,
    lowercase_read=True,
    load_dotenv=True,
    includes="config/*.yaml"
)
