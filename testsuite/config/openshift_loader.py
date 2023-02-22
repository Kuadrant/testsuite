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

    kcp = None
    if "kcp" in obj and "project" in obj["kcp"]:
        kcp_section = config["kcp"]
        kcp = client.change_project(kcp_section["project"] % None)
        # when advanced scheduling is enabled on kcp/syncer, status field is not synced back from workload cluster
        # deployment, is_ready method depends on status field that is not available yet hence we have to mock it
        kcp.is_ready = lambda _: True
    obj["kcp"] = kcp
