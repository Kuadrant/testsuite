"""Test for preexisting authorino bug issue:https://github.com/Kuadrant/testsuite/issues/69"""

import pytest
from weakget import weakget

from testsuite.openshift.authorino import AuthorinoCR

pytestmark = [pytest.mark.authorino, pytest.mark.standalone_only]


@pytest.fixture(scope="module")
def setup_authorino(openshift, blame, testconfig, module_label, request):
    """Authorino instance"""

    def _authorino(sharding_label):
        authorino = AuthorinoCR.create_instance(
            openshift,
            blame("authorino"),
            image=weakget(testconfig)["authorino"]["image"] % None,
            label_selectors=[f"sharding={sharding_label}", f"testRun={module_label}"],
        )
        request.addfinalizer(authorino.delete)
        authorino.commit()
        authorino.wait_for_ready()
        return authorino

    return _authorino


@pytest.mark.issue("https://github.com/Kuadrant/authorino/pull/349")
def test_preexisting_auth(
    setup_authorino, setup_authorization, setup_gateway, setup_route, exposer, wildcard_domain, blame
):  # pylint: disable=too-many-locals
    """
    Test:
        - Create AuthConfig A with wildcard
        - Create Authorino A which will reconcile A
        - Create Envoy for Authorino A
        - Delete Authorino
        - Create another Authorino B, which should not reconcile A
        - Create Envoy for Authorino B
        - Create AuthConfig B which will have specific host colliding with host A
        - Assert that AuthConfig B has the host ready and is completely reconciled
        - Make request to second envoy
        - Assert that request was processed by right authorino and AuthConfig
    """
    authorino = setup_authorino(sharding_label="A")
    gw = setup_gateway(authorino)
    route = setup_route(wildcard_domain, gw)
    setup_authorization(route, "A")

    authorino.delete()
    gw.delete()

    authorino2 = setup_authorino(sharding_label="B")
    gw2 = setup_gateway(authorino2)
    hostname = exposer.expose_hostname(blame("hostname"), gw2)
    route2 = setup_route(hostname.hostname, gw2)
    auth = setup_authorization(route2, "B")

    assert hostname.hostname in auth.model.status.summary.hostsReady
    response = hostname.client().get("/get")
    assert response.status_code == 200
    assert response.json()["headers"]["Header"] == '{"anything":"B"}'
