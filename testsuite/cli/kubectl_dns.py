"""Wrapper around kubectl-dns binary"""

import os
import subprocess


class KubectlDNS:
    """Wrapper on top of kubectl-dns binary"""

    def __init__(self, binary) -> None:
        super().__init__()
        self.binary = binary

    def run(self, *args, **kwargs):
        """Passes arguments to subprocess.run()"""
        args = (self.binary, *args)
        kwargs.setdefault("capture_output", True)
        kwargs.setdefault("text", True)

        if "env" in kwargs:
            env = os.environ.copy()
            env.update(kwargs["env"])
            kwargs["env"] = env

        return subprocess.run(args, **kwargs)  # pylint: disable= subprocess-run-check
