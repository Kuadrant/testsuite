"""Config map"""

from testsuite.openshift import OpenShiftObject


class ConfigMap(OpenShiftObject):
    """Kubernetes ConfigMap object"""

    @classmethod
    def create_instance(
        cls,
        openshift,
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
        return cls(model, context=openshift.context)

    def __getitem__(self, name):
        return self.model.data[name]

    def __contains__(self, name):
        return name in self.model.data

    def __setitem__(self, name, value):
        self.model.data[name] = value
