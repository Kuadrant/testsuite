"""Module containing helper classes for OpenShift objects (C)RUD"""
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from testsuite.openshift.client import OpenShiftClient


class RemoteMapping:
    """Dict-like interface to different types of OpenShift Objects"""

    def __init__(self, client: "OpenShiftClient", resource_name: str):
        self._client = client
        self._resource_name = resource_name

    def fetch_resource(self, name, *cmd_args: str, auto_raise: bool = True):
        """Executes command and returns output in yaml format"""
        args: List[str] = []
        args.extend([self._resource_name, name, "-o", "json", "--ignore-not-found=true"])
        args.extend(cmd_args)
        return self._client.do_action("get", *args, auto_raise=auto_raise, parse_output=True)

    def __iter__(self):
        """Return iterator for requested resource"""
        data = self._client.do_action("get", self._resource_name, parse_output=True)
        return iter(data["items"])

    def __getitem__(self, name):
        """Return requested resource as APIObject"""
        res = self.fetch_resource(name)
        if res is None:
            raise KeyError()
        return res

    def __contains__(self, name):
        res = self.fetch_resource(name)
        return res is not None

    def __delitem__(self, name):
        if name not in self:
            raise KeyError()
        self._client.do_action("delete", self._resource_name, name)
