# pylint: disable=line-too-long
"""
Help as of 0.2.3
Kuadrant configuration command line utility

Usage:
  kuadrantctl [command]

Available Commands:
  completion  Generate the autocompletion script for the specified shell
  generate    Commands related to kubernetes object generation
    gatewayapi  Generate Gataway API resources
        httproute   Generate Gateway API HTTPRoute from OpenAPI 3.0.X
    kuadrant    Generate Kuadrant resources
        authpolicy      Generate Kuadrant AuthPolicy from OpenAPI 3.0.X
        ratelimitpolicy Generate Kuadrant Rate Limit Policy from OpenAPI 3.0.X


  help        Help about any command
  version     Print the version number of kuadrantctl

Flags:
  -h, --help                   help for httproute
      --oas string             Path to OpenAPI spec file (in JSON or YAML format), URL, or '-' to read from standard input (required)
  -o, --output-format string   Output format: 'yaml' or 'json'. (default "yaml")

Global Flags:
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
