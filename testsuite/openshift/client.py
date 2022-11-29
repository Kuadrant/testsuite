"""This module implements an openshift interface with openshift oc client wrapper."""

import enum
import os
from functools import cached_property
from typing import Dict, Optional

import openshift as oc
from openshift import Context, Selector, OpenShiftPythonException

from testsuite.certificates import Certificate
from testsuite.openshift.types.routes import Routes
from testsuite.openshift.types.secrets import Secrets


class ServiceTypes(enum.Enum):
    """Service types enum."""

    CLUSTER_IP = "clusterip"
    EXTERNAL_NAME = "externalname"
    LOAD_BALANCER = "loadbalancer"
    NODE_PORT = "nodeport"


class OpenShiftClient:
    """OpenShiftClient is an interface to the official OpenShift python
    client."""

    # pylint: disable=too-many-public-methods

    def __init__(self, project: str, api_url: str = None, token: str = None, kubeconfig_path: str = None):
        self._project = project
        self._api_url = api_url
        self.token = token
        self._kubeconfig_path = kubeconfig_path

    def change_project(self, project):
        """Return new OpenShiftClient with a different project"""
        return OpenShiftClient(project, self._api_url, self.token, self._kubeconfig_path)

    @cached_property
    def context(self):
        """Prepare context for command execution"""
        context = Context()

        context.project_name = self._project
        context.api_url = self._api_url
        context.token = self.token
        context.kubeconfig_path = self._kubeconfig_path

        return context

    @property
    def api_url(self):
        """Returns real API url"""
        with self.context:
            return oc.whoami("--show-server=true")

    @property
    def project(self):
        """Returns real OpenShift project name"""
        with self.context:
            return oc.get_project_name()

    @property
    def connected(self):
        """Returns True, if user is logged in and the project exists"""
        try:
            self.do_action("status")
        except OpenShiftPythonException:
            return False
        return True

    @cached_property
    def routes(self):
        """Return dict-like interface for Routes"""
        return Routes(self)

    @cached_property
    def secrets(self):
        """Return dict-like interface for Secrets"""
        return Secrets(self)

    def do_action(self, verb: str, *args, auto_raise: bool = True, parse_output: bool = False):
        """Run an oc command."""
        with self.context:
            result = oc.invoke(verb, args, auto_raise=auto_raise)
            if parse_output:
                return oc.APIObject(string_to_model=result.out())
            return result

    @property
    def project_exists(self):
        """Returns True if the project exists"""
        try:
            self.do_action("get", f"project/{self.project}")
            return True
        except oc.OpenShiftPythonException:
            return False

    def new_app(self, source, params: Dict[str, str] = None):
        """Create application based on source code.

        Args:
            :param source: The source of the template, it must be either an url or a path to a local file.
            :param params: The parameters to be passed to the source when building it.
        """
        opt_args = []
        if params:
            opt_args.extend([f"--param={n}={v}" for n, v in params.items()])

        if os.path.isfile(source):
            source = f"--filename={source}"
            opt_args.append("--local=true")
        objects = self.do_action("process", source, opt_args).out()
        with self.context:
            created = oc.create(objects)
        return created

    def is_ready(self, selector: Selector):
        """
        Returns true, if the selector pointing to Deployments or DeploymentConfigs are ready
        Requires to be run inside context
        """
        success, _, _ = selector.until_all(success_func=lambda obj: "readyReplicas" in obj.model.status)
        return success

    def create_tls_secret(self, name: str, certificate: Certificate, labels: Optional[Dict[str, str]] = None):
        """Creates a TLS secret"""
        model: Dict = {
            'kind': 'Secret',
            'apiVersion': 'v1',
            'metadata': {
                'name': name,
            },
            'stringData': {
                "tls.crt": certificate.chain or certificate.certificate,
                "tls.key": certificate.key
            },
            "type": "kubernetes.io/tls"
        }
        if labels is not None:
            model["metadata"]["labels"] = labels

        with self.context:
            return oc.create(model, ["--save-config=true"])

    def delete_selector(self, selector, ignore_not_found=True):
        """Deletes all resources from selectior"""
        with self.context:
            selector.delete(ignore_not_found=ignore_not_found)
