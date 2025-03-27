"""API Key Secret CR object"""

import base64
from functools import cached_property

from testsuite.kubernetes.client import KubernetesClient
from testsuite.kubernetes import KubernetesObject, modify, Selector


class APIKey(KubernetesObject):
    """Represents API Key Secret CR for Authorino"""

    def __init__(self, value, label, dict_to_model=None, string_to_model=None, context=None):
        self.label = label
        self.value = value
        super().__init__(dict_to_model, string_to_model, context)

    def __str__(self):
        return base64.b64decode(self.model.data["api_key"]).decode("utf-8")

    @classmethod
    def create_instance(cls, cluster: KubernetesClient, name, label, api_key, annotations: dict[str, str] = None):
        """Creates base instance"""
        model = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": name,
                "namespace": cluster.project,
                "labels": {"authorino.kuadrant.io/managed-by": "authorino", "group": label},
                "annotations": annotations if annotations is not None else {},
            },
            "stringData": {"api_key": api_key},
            "type": "Opaque",
        }

        return cls(api_key, label, dict_to_model=model, context=cluster.context)

    @cached_property
    def selector(self):
        """Return Selector for this ApiKey"""
        return Selector(matchLabels={"group": self.label})

    @modify
    def update_api_key(self, api_key):
        """Updates API key Secret with new API key"""
        self.model.data["api_key"] = base64.b64encode(api_key.encode("utf-8")).decode("ascii")
