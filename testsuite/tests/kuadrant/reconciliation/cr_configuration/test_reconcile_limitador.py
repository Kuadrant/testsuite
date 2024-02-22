"""Tests for Kuadrant sub component - Limitador CR configuration via Kuadrant CR"""

import pytest

pytestmark = [pytest.mark.kuadrant_only]


REPLICAS_1 = {"replicas": 1}
REPLICAS_2 = {"replicas": 2}


@pytest.fixture(scope="module", autouse=True)
def kuadrant_clean_up(request, kuadrant):
    """Return the number of replicas for Limitador back to 1"""
    request.addfinalizer(lambda: kuadrant.update_limitador(REPLICAS_1))


def test_spec_config(kuadrant):
    """
    Test:
        - assert that Limitador deployment replicas is equal to 1
        - change replicas field to 2 in Kuadrant CR
        - assert that Kuadrant CR Limitador replicas is equal to 2
        - assert that Limitador deployment replicas is equal to 2
    """
    assert kuadrant.limitador["replicas"] == 1, "The number of Limitador replicas in KuadrantCR should be 1 "
    assert kuadrant.limitador_deployment.model.spec.replicas == 1, "Limitador deployment should use 1 replica"

    kuadrant.update_limitador(REPLICAS_2)

    assert kuadrant.limitador["replicas"] == 2
    assert kuadrant.limitador_deployment.model.spec.replicas == 2


def test_unsupported_spec_field(kuadrant):
    """
    Tests that unsupported field is not reconciled
    """
    kuadrant.update_limitador({"test": "test"})
    kuadrant.refresh()

    assert "test" not in kuadrant.limitador
    assert "test" not in kuadrant.limitador_deployment.model.spec
