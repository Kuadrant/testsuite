"""Config map"""

from testsuite.kubernetes import KubernetesObject


class ConfigMap(KubernetesObject):
    """Kubernetes ConfigMap object"""

    @classmethod
    def create_instance(
        cls,
        cluster,
        name,
        data: dict[str, str],
        labels: dict[str, str] = None,
    ):
        """Creates new Config Map"""
        model: dict = {
            "kind": "ConfigMap",
            "apiVersion": "v1",
            "metadata": {
                "name": name,
                "labels": labels,
            },
            "data": data,
        }
        return cls(model, context=cluster.context)

    def __getitem__(self, name):
        return self.model.data[name]

    def __contains__(self, name):
        return name in self.model.data

    def __setitem__(self, name, value):
        self.model.data[name] = value
