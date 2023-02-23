"""Conftest for metadata feature tests"""
import pytest

from testsuite.openshift.objects import OpenShiftObject


@pytest.fixture(scope="module")
def create_client_secret(request, openshift):
    """Creates Client Secret, used by Authorino to start the authentication with the UMA registry"""

    def _create_secret(name, client_id, client_secret):
        model = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": name,
            },
            "stringData": {"clientID": client_id, "clientSecret": client_secret},
            "type": "Opaque",
        }
        secret = OpenShiftObject(model, context=openshift.context)
        request.addfinalizer(lambda: secret.delete(ignore_not_found=True))
        secret.commit()
        return secret

    return _create_secret
