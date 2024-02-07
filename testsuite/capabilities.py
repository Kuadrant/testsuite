"""Contains capability related classes"""

import functools

from weakget import weakget

from testsuite.config import settings


@functools.cache
def has_kuadrant():
    """Returns True, if Kuadrant deployment is present and should be used"""
    spokes = weakget(settings)["control_plane"]["spokes"] % {}

    for name, openshift in spokes.items():
        # Try if Kuadrant is deployed
        if not openshift.connected:
            return False, f"Spoke {name} is not connected"
        project = settings["service_protection"]["system_project"]
        kuadrant_openshift = openshift.change_project(project)
        kuadrants = kuadrant_openshift.do_action("get", "kuadrant", "-o", "json", parse_output=True)
        if len(kuadrants.model["items"]) == 0:
            return False, f"Spoke {name} does not have Kuadrant resource in project {project}"

    return True, None


@functools.cache
def has_mgc():
    """Returns True, if MGC is configured and deployed"""
    spokes = weakget(settings)["control_plane"]["spokes"] % {}

    if len(spokes) == 0:
        return False, "Spokes are not configured"

    hub_openshift = settings["control_plane"]["hub"]
    if not hub_openshift.connected:
        return False, "Control Plane Hub Openshift is not connected"

    if "managedzones" not in hub_openshift.do_action("api-resources", "--api-group=kuadrant.io").out():
        return False, "MGC custom resources are missing on hub cluster"
    return True, None
