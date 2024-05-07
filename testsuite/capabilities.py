"""Contains capability related classes"""

import functools

from weakget import weakget

from testsuite.config import settings


@functools.cache
def has_kuadrant():
    """Returns True, if Kuadrant deployment is present and should be used"""
    if spokes := weakget(settings)["control_plane"]["spokes"] % {}:
        for name, openshift in spokes.items():
            # Try if Kuadrant is deployed
            if not openshift.connected:
                return False, f"Spoke {name} is not connected"
            project = settings["service_protection"]["system_project"]
            kuadrant_openshift = openshift.change_project(project)
            kuadrants = kuadrant_openshift.do_action("get", "kuadrant", "-o", "json", parse_output=True)
            if len(kuadrants.model["items"]) == 0:
                return False, f"Spoke {name} does not have Kuadrant resource in project {project}"

    else:
        openshift = settings["service_protection"]["project"]
        project = settings["service_protection"]["system_project"]
        kuadrant_openshift = openshift.change_project(project)
        kuadrants = kuadrant_openshift.do_action("get", "kuadrant", "-o", "json", parse_output=True)
        if len(kuadrants.model["items"]) == 0:
            return False, f"Kuadrant resource is not installed in project {project}"

    return True, None
