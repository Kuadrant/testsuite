"""
kuadrantctl v0.5.0
Kuadrant configuration command line utility

Usage:
  kuadrantctl [command]

Available Commands:
  completion  Generate the autocompletion script for the specified shell
  generate    Commands related to kubernetes object generation
  help        Help about any command
  topology    Export and visualize Kuadrant topology
  version     Print the version number of kuadrantctl

Flags:
  -h, --help      help for kuadrantctl
  -v, --verbose   verbose output

Use "kuadrantctl [command] --help" for more information about a command.
"""

import subprocess


class KuadrantCTL:
    """Wrapper on top of kuadrantctl binary"""

    def __init__(self, binary) -> None:
        super().__init__()
        self.binary = binary

    def run(self, *args, **kwargs):
        """Passes arguments to Subprocess.run, see that for more details"""
        args = (self.binary, *args)
        kwargs.setdefault("capture_output", True)
        kwargs.setdefault("check", True)
        kwargs.setdefault("text", True)
        # We do supply value for check :)
        return subprocess.run(args, **kwargs)  # pylint: disable= subprocess-run-check
