"""Tests for Kuadrant sub component - Limitador CR configuration via Kuadrant CR"""

import pytest

from testsuite.openshift.deployment import ContainerResources
from testsuite.utils import asdict

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
        kuadrant.limitador["replicas"] = 1
        kuadrant.limitador["resourceRequirements"] = ContainerResources(requests_cpu="250m", requests_memory="32Mi")
        kuadrant.safe_apply()
        kuadrant.wait_for_ready()

    request.addfinalizer(_finalize)


def test_replicas_field_to_reconcile(kuadrant):
    """
    Test:
        - change replicas field to 2 in Kuadrant CR
        - assert that replicas field in Kuadrant CR spec.limitador and Limitador deployment is equal to 2
    """
    kuadrant.limitador["replicas"] = 2
    kuadrant.safe_apply()
    kuadrant.wait_for_ready()

    assert kuadrant.limitador["replicas"] == 2
    assert kuadrant.limitador_deployment.model.spec["replicas"] == 2


def test_resource_requirements_field_to_reconcile(kuadrant):
    """
    Test:
        - change resourceRequirements field to `value` in Kuadrant CR
        - assert that resourceRequirements field in Kuadrant CR spec.limitador and Limitador deployment
          is equal to `value`
    """
    value = ContainerResources(requests_cpu="300m", requests_memory="40Mi")

    kuadrant.limitador["resourceRequirements"] = value
    kuadrant.safe_apply()
    kuadrant.wait_for_ready()

    assert kuadrant.limitador["resourceRequirements"] == asdict(value)
    assert kuadrant.limitador_deployment.model.spec.template.spec.containers[0]["resources"] == asdict(value)


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
    kuadrant.limitador["replicas"] = 2
    kuadrant.limitador["resourceRequirements"] = ContainerResources(requests_cpu="300m", requests_memory="40Mi")
    kuadrant.safe_apply()
    kuadrant.wait_for_ready()

    kuadrant.limitador["replicas"] = 3
    kuadrant.safe_apply()
    kuadrant.wait_for_ready()

    assert kuadrant.limitador_deployment.model.spec.replicas == 3
    assert kuadrant.limitador_deployment.model.spec.template.spec.containers[0]["resources"] == asdict(
        ContainerResources(requests_cpu="250m", requests_memory="32Mi")
    )
