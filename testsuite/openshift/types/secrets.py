"""Module containing classes for manipulation with OpenShift secrets"""
import base64

from testsuite.openshift.types import RemoteMapping


class Secrets(RemoteMapping):
    """Dict-like interface to openshift secrets"""

    def __init__(self, client):
        super().__init__(client, "secret")

    def __getitem__(self, name: str):
        """Return requested secret in yaml format"""

        # pylint: disable=too-few-public-methods
        class _DecodedSecrets:

            def __init__(self, data):
                self._data = data

            def __getitem__(self, name):
                return base64.b64decode(self._data[name]).decode("utf-8")

            def __contains__(self, name):
                return name in self._data

        return _DecodedSecrets(super().__getitem__(name).model.data)
