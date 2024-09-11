"""Contains capability related classes"""

import functools

from openshift_client import selector

from testsuite.config import settings


@functools.cache
def has_kuadrant():
    """Returns True, if Kuadrant deployment is present and should be used"""
    project = settings["service_protection"]["system_project"]
    clusters = [settings["control_plane"]["cluster"]]
    if cluster2 := settings["control_plane"]["cluster2"]:
        clusters.append(cluster2)
    for cluster in clusters:
        system_project = cluster.change_project(project)
        if not system_project.connected:
            return False, f"Cluster {cluster.api_url} is not connected, or namespace {project} does not exist"

        with system_project.context:
            if selector("kuadrant").count_existing() == 0:
                return False, f"Cluster {cluster.api_url} does not have Kuadrant resource in project {project}"

    return True, None
