"""This module implements an KubernetesCLI interface using oc/kubectl binary commands."""

from functools import cached_property
from urllib.parse import urlparse

import openshift_client as oc
from openshift_client import Context, OpenShiftPythonException

from testsuite.kubernetes.openshift.route import OpenshiftRoute
from testsuite.kubernetes.service import Service
from .deployment import Deployment
from .secret import Secret


class KubernetesClient:
    """KubernetesClient is a helper class for invoking kubectl commands"""

    # pylint: disable=too-many-public-methods

    def __init__(self, project: str = None, api_url: str = None, token: str = None, kubeconfig_path: str = None):
        self._project = project
        self._api_url = api_url
        self._token = token
        self._kubeconfig_path = kubeconfig_path

    @classmethod
    def from_context(cls, context: Context) -> "KubernetesClient":
        """Creates self from the context"""
        return cls(context.get_project(), context.get_api_url(), context.get_token(), context.get_kubeconfig_path())

    def change_project(self, project) -> "KubernetesClient":
        """Return new self with a different project"""
        return KubernetesClient(project, self._api_url, self._token, self._kubeconfig_path)

    @cached_property
    def context(self):
        """Prepare context for command execution"""
        context = Context()

        context.project_name = self._project
        context.api_server = self._api_url
        context.token = self._token
        context.kubeconfig_path = self._kubeconfig_path

        return context

    @property
    def api_url(self):
        """Returns real API url"""
        return self._api_url or self.inspect_context(jsonpath="{.clusters[*].cluster.server}")

    @property
    def token(self):
        """Returns real Kubernetes token"""
        return self._token or self.inspect_context(jsonpath="{.users[*].user.token}", raw=True)

    @cached_property
    def apps_url(self):
        """Return URL under which all routes are routed"""
        hostname = urlparse(self.api_url).hostname
        return "apps." + hostname.split(".", 1)[1]

    @property
    def project(self):
        """Returns real Kubernetes namespace name"""
        with self.context:
            return oc.get_project_name()

    @property
    def connected(self):
        """Returns True, if user is logged in and the project exists"""
        try:
            self.do_action("get", "ns", self._project)
        except OpenShiftPythonException:
            return False
        return True

    def get_secret(self, name):
        """Returns dict-like structure for accessing secret data"""
        with self.context:
            return oc.selector(f"secret/{name}").object(cls=Secret)

    def service_exists(self, name) -> bool:
        """Returns True if service with the given name exists"""
        with self.context:
            return oc.selector(f"svc/{name}").count_existing() == 1

    def get_route(self, name):
        """Returns dict-like structure for accessing secret data"""
        with self.context:
            return oc.selector(f"route/{name}").object(cls=OpenshiftRoute)

    def get_routes_for_service(self, service_name: str) -> list[OpenshiftRoute]:
        """Returns list of routes for given service"""
        with self.context:
            return oc.selector("route", field_selectors={"spec.to.name": service_name}).objects(cls=OpenshiftRoute)

    def get_service(self, service_name: str):
        """Returns dict-like structure for accessing service data"""
        with self.context:
            return oc.selector(f"service/{service_name}").object(cls=Service)

    def get_deployment(self, name: str):
        """Returns dict-like structure for accessing deployment data"""
        with self.context:
            return oc.selector(f"deployment/{name}").object(cls=Deployment)

    def do_action(self, verb: str, *args, stdin_str=None, auto_raise: bool = True, parse_output: bool = False):
        """Run an oc command."""
        with self.context:
            result = oc.invoke(verb, args, stdin_str=stdin_str, auto_raise=auto_raise)
            if parse_output:
                return oc.APIObject(string_to_model=result.out())
            return result

    def inspect_context(self, jsonpath, raw=False):
        """Returns jsonpath from the current context"""
        return (
            self.do_action("config", "view", f'--output=jsonpath="{jsonpath}"', f"--raw={raw}", "--minify=true")
            .out()
            .replace('"', "")
            .strip()
        )

    @property
    def project_exists(self):
        """Returns True if the project exists"""
        try:
            self.do_action("get", f"project/{self.project}")
            return True
        except oc.OpenShiftPythonException:
            return False

    def apply_from_string(self, string, cls, cmd_args=None):
        """Applies new object from the string to the server and returns it wrapped in the class"""
        with self.context:
            selector = oc.apply(string, cmd_args=cmd_args)
            obj = selector.object(cls=cls)
            obj.context = self.context
        return obj
