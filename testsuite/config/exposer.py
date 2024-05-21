"""Translates string to an Exposer class that can initialized"""

from testsuite.gateway.exposers import OpenShiftExposer, KindExposer

EXPOSERS = {"openshift": OpenShiftExposer, "kind": KindExposer}


# pylint: disable=unused-argument
def load(obj, env=None, silent=True, key=None, filename=None):
    """Selects proper Exposes class"""
    try:
        obj["default_exposer"] = EXPOSERS[obj["default_exposer"]]
    except KeyError:
        pass
