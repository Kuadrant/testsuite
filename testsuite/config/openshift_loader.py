"""Custom dynaconf loader for loading cluster settings and converting them to KubernetesClients"""

from testsuite.kubernetes.client import KubernetesClient


def inject_client(obj, base_client, path):
    """Injects KubernetesClient in the settings, changes only project"""
    original = obj.get(path, None)
    if original:
        obj[path] = base_client.change_project(original)
    else:
        obj[path] = base_client


# pylint: disable=unused-argument, too-many-locals
def load(obj, env=None, silent=True, key=None, filename=None):
    """Creates all KubernetesClients"""
    control_plane = obj.setdefault("control_plane", {})

    cluster = control_plane.setdefault("cluster", {})
    client = KubernetesClient(
        cluster.get("project"), cluster.get("api_url"), cluster.get("token"), cluster.get("kubeconfig_path")
    )
    obj["control_plane"]["cluster"] = client

    tools = None
    if "tools" in obj and "project" in obj["tools"]:
        tools = client.change_project(obj["tools"]["project"])
    obj["tools"] = tools

    clients = []
    clusters = control_plane.setdefault("additional_clusters", [])
    for value in clusters:
        clients.append(
            KubernetesClient(
                value.get("project"), value.get("api_url"), value.get("token"), value.get("kubeconfig_path")
            )
        )
    if len(clients) > 0:
        control_plane["additional_clusters"] = clients

    if cluster2 := control_plane.setdefault("cluster2", {}):
        obj["control_plane"]["cluster2"] = KubernetesClient(
            cluster2.get("project"), cluster2.get("api_url"), cluster2.get("token"), cluster2.get("kubeconfig_path")
        )

    if cluster3 := control_plane.setdefault("cluster3", {}):
        obj["control_plane"]["cluster3"] = KubernetesClient(
            cluster3.get("project"), cluster3.get("api_url"), cluster3.get("token"), cluster3.get("kubeconfig_path")
        )
