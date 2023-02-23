"""Test for preexisting authorino bug issue:https://github.com/Kuadrant/testsuite/issues/69"""

import pytest
from weakget import weakget

from testsuite.openshift.objects.authorino import AuthorinoCR


@pytest.fixture(scope="module")
def authorino(openshift, blame, testconfig, module_label, request):
    """Authorino instance"""

    def _authorino(sharding_label):
        authorino_parameters = {"label_selectors": [f"sharding={sharding_label}", f"testRun={module_label}"]}
        authorino = AuthorinoCR.create_instance(
            openshift,
            blame("authorino"),
            image=weakget(testconfig)["authorino"]["image"] % None,
            **authorino_parameters,
        )
        request.addfinalizer(lambda: authorino.delete(ignore_not_found=True))
        authorino.commit()
        authorino.wait_for_ready()
        return authorino

    return _authorino


@pytest.fixture(scope="module")
def setup(authorino, authorization, envoy, wildcard_domain):
    """
    Setup:
        - Create AuthConfig A with wildcard
        - Create Authorino A which will reconcile A
        - Create Envoy for Authorino A
        - Delete Authorino
        - Create another Authorino B, which should not reconcile A
        - Create Envoy for Authorino B
        - Create AuthConfig B which will have specific host colliding with host A
    """
    authorization(wildcard_domain, "A")
    custom_authorino = authorino(sharding_label="A")
    envoy(custom_authorino)

    custom_authorino.delete()

    custom_authorino2 = authorino(sharding_label="B")
    custom_envoy = envoy(custom_authorino2)
    auth = authorization(custom_envoy.hostname, "B")

    return custom_envoy, auth


@pytest.mark.issue("https://github.com/Kuadrant/authorino/pull/349")
def test_preexisting_auth(setup):
    """
    Test:
        - Assert that AuthConfig B has the host ready and is completely reconciled
        - Make request to second envoy
        - Assert that request was processed by right authorino and AuthConfig
    """
    envoy, auth = setup
    assert envoy.hostname in auth.model.status.summary.hostsReady
    response = envoy.client().get("/get")
    assert response.status_code == 200
    assert response.json()["headers"]["Header"] == '{"anything":"B"}'
