"""Contains capability related classes"""

import functools

from weakget import weakget

from testsuite.config import settings


@functools.cache
def has_kuadrant():
    """Returns True, if Kuadrant deployment is present and should be used"""
    project = settings["service_protection"]["system_project"]
    if clusters := weakget(settings)["control_plane"]["additional_clusters"] % []:
        for openshift in clusters:
            name = openshift.api_url
            # Try if Kuadrant is deployed
            if not openshift.connected:
                return False, f"Cluster {name} is not connected"
            kuadrant_openshift = openshift.change_project(project)
            kuadrants = kuadrant_openshift.do_action("get", "kuadrant", "-o", "json", parse_output=True)
            if len(kuadrants.model["items"]) == 0:
                return False, f"Cluster {name} does not have Kuadrant resource in project {project}"

    else:
        openshift = settings["cluster"]
        kuadrant_openshift = openshift.change_project(project)
        kuadrants = kuadrant_openshift.do_action("get", "kuadrant", "-o", "json", parse_output=True)
        if len(kuadrants.model["items"]) == 0:
            return False, f"Kuadrant resource is not installed in project {project}"

    return True, None
