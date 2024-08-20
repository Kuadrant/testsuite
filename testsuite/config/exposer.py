"""Translates string to an Exposer class that can initialized"""

from testsuite.gateway.exposers import OpenShiftExposer, LoadBalancerServiceExposer

EXPOSERS = {"openshift": OpenShiftExposer, "kind": LoadBalancerServiceExposer, "kubernetes": LoadBalancerServiceExposer}


# pylint: disable=unused-argument
def load(obj, env=None, silent=True, key=None, filename=None):
    """Selects proper Exposes class"""
    if "default_exposer" not in obj or not obj["default_exposer"]:
        client = obj["control_plane"]["cluster"]
        if "route.openshift.io/v1" in client.do_action("api-versions").out():
            obj["default_exposer"] = EXPOSERS["openshift"]
        else:
            obj["default_exposer"] = EXPOSERS["kubernetes"]
    else:
        obj["default_exposer"] = EXPOSERS[obj["default_exposer"]]
