"""Module containing classes for manipulation with OpenShift routes"""
from testsuite.openshift.types import RemoteMapping


class Routes(RemoteMapping):
    """Dict-like interface to OpenShift routes"""

    def __init__(self, client) -> None:
        super().__init__(client, "route")

    def expose(self, name, service, hostname=None, port=None):
        """Expose containers internally as services or externally via routes.
        Returns requested route in yaml format.
        """
        extra_args = []
        if hostname is not None:
            extra_args.append(f"--hostname={hostname}")
        if port is not None:
            extra_args.append(f"--port={port}")
        return self._client.do_action(
            "expose", "service", f"--name={name}", "-o", "json", service, *extra_args, parse_output=True
        )
