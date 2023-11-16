"""Custom dynaconf loader for loading OpenShift settings and converting them to OpenshiftClients"""

from testsuite.openshift.client import OpenShiftClient


def inject_client(obj, base_client, path):
    """Injects OpenShiftClient in the settings, changes only project"""
    original = obj.get(path, None)
    if original:
        obj[path] = base_client.change_project(original)
    else:
        obj[path] = base_client


# pylint: disable=unused-argument, too-many-locals
def load(obj, env=None, silent=True, key=None, filename=None):
    """Creates all OpenShift clients"""
    section = obj.setdefault("cluster", {})
    client = OpenShiftClient(
        section.get("project"), section.get("api_url"), section.get("token"), section.get("kubeconfig_path")
    )
    obj["cluster"] = client

    tools = None
    if "tools" in obj and "project" in obj["tools"]:
        tools = client.change_project(obj["tools"]["project"])
    obj["tools"] = tools

    service_protection = obj.setdefault("service_protection", {})
    inject_client(service_protection, client, "system_project")
    inject_client(service_protection, client, "project")
    inject_client(service_protection, client, "project2")

    control_plane = obj.setdefault("control_plane", {})
    hub = control_plane.get("hub", {})
    hub_client = OpenShiftClient(hub.get("project"), hub.get("api_url"), hub.get("token"), hub.get("kubeconfig_path"))
    obj["control_plane"]["hub"] = hub_client

    clients = {}
    spokes = control_plane.setdefault("spokes", {})
    for name, value in spokes.items():
        clients[name] = OpenShiftClient(
            value.get("project"), value.get("api_url"), value.get("token"), value.get("kubeconfig_path")
        )
    if len(clients) > 0:
        control_plane["spokes"] = clients
