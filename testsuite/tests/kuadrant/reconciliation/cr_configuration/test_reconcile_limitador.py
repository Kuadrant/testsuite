"""Tests for Kuadrant sub component - Limitador CR configuration via Kuadrant CR"""

import pytest


REPLICAS_1 = {"replicas": 1}
REPLICAS_2 = {"replicas": 2}


@pytest.fixture(scope="module")
def kuadrant(request, kuadrant):
    """Return the number of replicas for Limitador back to 1"""
    request.addfinalizer(lambda: kuadrant.set_limitador(REPLICAS_1))
    return kuadrant


def get_limitador_spec(kuadrant_client):
    """Gets Limitador CR and returns its spec section from API object"""
    limitador_cr = kuadrant_client.do_action("get", "limitador", "-o", "json", parse_output=True)
    return limitador_cr.model["items"][0].spec


def test_spec_config(kuadrant, kuadrant_client):
    """
    Test:
        - assert that both Limitador CR and deployment replicas are equal to 1
        - change replicas field to 2 in Kuadrant CR
        - assert that Kuadrant CR Limitador replicas are equal to 2
        - assert that both Limitador CR and deployment replicas are equal to 2
    """
    assert get_limitador_spec(kuadrant_client).replicas == 1, ""
    assert kuadrant.limitador_deployment.model.spec.replicas == 1, ""

    kuadrant.set_limitador(REPLICAS_2)

    kuadrant_cr = kuadrant_client.get_kuadrant("kuadrant-sample")
    assert kuadrant_cr.model.spec.limitador["replicas"] == 2

    assert get_limitador_spec(kuadrant_client).replicas == 2
    assert kuadrant.limitador_deployment.model.spec.replicas == 2, ""


def test_unsupported_spec_field(kuadrant, kuadrant_client):
    """
    Tests that unsupported field is not reconciled
    """
    kuadrant.set_limitador({"test": "test"})

    kuadrant_cr = kuadrant_client.get_kuadrant("kuadrant-sample")
    assert "test" not in kuadrant_cr.model.spec.limitador

    assert "test" not in get_limitador_spec(kuadrant_client)
