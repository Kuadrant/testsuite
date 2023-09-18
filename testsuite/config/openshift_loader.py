"""Custom dynaconf loader for loading OpenShift settings and converting them to OpenshiftClients"""
from weakget import weakget

from testsuite.openshift.client import OpenShiftClient


# pylint: disable=unused-argument
def load(obj, env=None, silent=True, key=None, filename=None):
    """Creates all OpenShift clients"""
    config = weakget(obj)
    section = config["openshift"]
    client = OpenShiftClient(
        section["project"] % None, section["api_url"] % None, section["token"] % None, section["kubeconfig_path"] % None
    )
    obj["openshift"] = client

    tools = None
    if "tools" in obj and "project" in obj["tools"]:
        tools = client.change_project(obj["tools"]["project"])
    obj["tools"] = tools

    openshift2 = None
    if "openshift2" in obj and "project" in obj["openshift2"]:
        openshift2 = client.change_project(obj["openshift2"]["project"])
    obj["openshift2"] = openshift2

    clients = {}
    spokes = weakget(obj)["mgc"]["spokes"] % {}
    for name, value in spokes.items():
        value = weakget(value)
        clients[name] = OpenShiftClient(
            value["project"] % None, value["api_url"] % None, value["token"] % None, value["kubeconfig_path"] % None
        )
    if len(clients) > 0:
        obj["mgc"]["spokes"] = clients
