"""This module implements an openshift interface with openshift oc client wrapper."""

import enum
import os
from functools import cached_property
from typing import Dict, Union, Sequence

import openshift as oc
from openshift import Context


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

    def __init__(self, project: str, api_url: str = None, token: str = None):
        self._project = project
        self._api_url = api_url
        self.token = token

    @cached_property
    def context(self):
        """Prepare context for command execution"""
        context = Context()
        context.project_name = self._project
        context.api_url = self._api_url
        context.token = self.token
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

    def do_action(self, verb: str, cmd_args: Sequence[Union[str, Sequence[str]]] = None,
                  auto_raise: bool = True, parse_output: bool = False):
        """Run an oc command."""
        cmd_args = cmd_args or []
        with self.context:
            result = oc.invoke(verb, cmd_args, auto_raise=auto_raise)
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
        objects = self.do_action("process", [source, opt_args]).out()
        with self.context:
            created = oc.create(objects)
        return created
