"""Tests for Kuadrant sub component - Limitador CR configuration via Kuadrant CR"""

import pytest

pytestmark = [pytest.mark.kuadrant_only]


@pytest.fixture()
def commit():
    """Omitting authorization and rate limiting as it is not needed"""


@pytest.fixture(autouse=True)
def kuadrant_clean_up(request, kuadrant):
    """
    Return fields to default values.
    This can be simplified once https://github.com/Kuadrant/kuadrant-operator/issues/617 is fixed.
    """

    def _finalize():
        kuadrant.limitador = {"replicas": 1, "resourceRequirements": {"requests": {"cpu": "250m", "memory": "32Mi"}}}

    request.addfinalizer(_finalize)


@pytest.mark.parametrize(
    "field, value",
    [
        pytest.param("replicas", 2, id="replicas"),
        pytest.param(
            "resourceRequirements", {"requests": {"cpu": "300m", "memory": "40Mi"}}, id="resourceRequirements"
        ),
    ],
)
def test_fields_to_reconcile(kuadrant, field, value):
    """
    Test:
        - change specific `field` to `value` in Kuadrant CR
        - assert that `field` in Kuadrant CR Limitador is equal to `value`
        - assert that `field` in Limitador deployment is equal to `value`
    """
    kuadrant.limitador = {field: value}

    assert value == kuadrant.limitador[field]
    assert str(value) in str(kuadrant.limitador_deployment.model.spec)


@pytest.mark.xfail
@pytest.mark.issue("https://github.com/Kuadrant/kuadrant-operator/issues/617")
def test_blank_fields_wont_reconcile(kuadrant):
    """
    Test:
        - setup limitador with replicas and resourceRequirements != default
        - change replicas to 3
        - assert replicas field is 3 for limitador deployment
        - assert blank field resourceRequirements is returned to default for limitador deployment
    """
    kuadrant.limitador = {"replicas": 2, "resourceRequirements": {"requests": {"cpu": "300m", "memory": "40Mi"}}}

    kuadrant.limitador = {"replicas": 3}

    assert kuadrant.limitador_deployment.model.spec.replicas == 3
    assert "'cpu': '250m', 'memory': '32Mi'" in str(kuadrant.limitador_deployment.model.spec)
