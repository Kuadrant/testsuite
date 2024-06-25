"""OAS processing"""

import contextlib
import json
import tempfile
from collections import UserDict

import yaml

from testsuite.backend import Backend
from testsuite.gateway import Referencable, Hostname


@contextlib.contextmanager
def as_tmp_file(text):
    """Saves text in a temporary file and returns absolute path"""
    with tempfile.NamedTemporaryFile("w") as file:
        file.write(text)
        file.flush()
        yield file.name


class OASWrapper(UserDict):
    """Wrapper for OpenAPISpecification"""

    def as_json(self):
        """Returns OAS as JSON"""
        return json.dumps(self.data)

    def as_yaml(self):
        """Returns OAS as YAML"""
        return yaml.dump(self.data)

    def add_backend_to_paths(self, backend: Backend):
        """Adds backend to all paths, should be only used in tests that do not test this section"""
        for path in self["paths"].values():
            path["x-kuadrant"] = {
                "backendRefs": [backend.reference],
            }

    def add_top_level_route(self, parent: Referencable, hostname: Hostname, name: str):
        """Adds top-level x-kuadrant definition for Route, should be only used in tests that do not test this section"""
        self["x-kuadrant"] = {
            "route": {
                "name": name,
                "hostnames": [hostname.hostname],
                "parentRefs": [parent.reference],
            }
        }
