"""Conftest for Kuadrant distributed tracing tests."""

import pytest

from openshift_client import selector
from testsuite.kuadrant import (
    ObservabilityOptions,
    ObservabilityTracingOptions,
    DataPlaneOptions,
    DataPlaneDefaultLevels,
)
from testsuite.kuadrant.authorino import TracingOptions as AuthorinoTracingOptions
from testsuite.kuadrant.limitador import TracingOptions as LimitadorTracingOptions
from testsuite.istio import IstioCR, Telemetry


@pytest.fixture(scope="module", autouse=True)
def authorino(kuadrant, request, tracing):
    """
    Enables OpenTelemetry tracing for the Authorino authorization service,
    pointing to the configured tracing backend.
    Registers a finalizer to reset tracing configuration after tests complete.
    """
    authorino = kuadrant.authorino
    request.addfinalizer(authorino.reset_tracing)
    authorino.set_tracing(AuthorinoTracingOptions(endpoint=tracing.collector_url, insecure=tracing.insecure))
    authorino.wait_for_ready()
    return authorino


@pytest.fixture(scope="module", autouse=True)
def limitador(kuadrant, request, tracing):
    """
    Enables OpenTelemetry tracing for the Limitador rate limiting service.
    Registers a finalizer to reset tracing configuration after tests complete.
    """
    limitador = kuadrant.limitador
    request.addfinalizer(limitador.reset_tracing)
    limitador.set_tracing(LimitadorTracingOptions(endpoint=tracing.collector_url))
    limitador.wait_for_ready()
    return limitador


@pytest.fixture(scope="module", autouse=True)
def enable_istio_tracing(cluster, testconfig, request, skip_or_fail):
    """
    Configures the Istio control plane (via Sail Operator's Istio CR) to send
    traces to the Jaeger collector using the jaeger-otlp provider on port 4317.
    Skips tests if Istio CR is not found (Sail Operator not installed).

    Registers a finalizer to reset Istio tracing configuration after tests complete.
    """
    istio_project = cluster.change_project(testconfig["service_protection"]["gateway"].get("project", "istio-system"))

    with istio_project.context:
        istio_cr = selector("istio/default").object(cls=IstioCR, ignore_not_found=True)
        if not istio_cr:
            skip_or_fail("Istio CR not found - Sail Operator may not be installed")

        service = "jaeger-collector.tools.svc.cluster.local"
        port = 4317

        istio_cr.set_tracing(service=service, port=port, provider_name="jaeger-otlp")

    def _reset():
        """Reset Istio tracing configuration"""
        with istio_project.context:
            istio_cr_reset = selector("istio/default").object(cls=IstioCR, ignore_not_found=True)
            if istio_cr_reset:
                istio_cr_reset.reset_tracing()

    request.addfinalizer(_reset)


@pytest.fixture(scope="module", autouse=True)
def mesh_telemetry(cluster, testconfig, request, blame):
    """
    Creates a Telemetry custom resource in the istio-system namespace to enable
    distributed tracing across the entire service mesh.
    Registers a finalizer to delete the resource after tests.
    """
    istio_project = cluster.change_project(testconfig["service_protection"]["gateway"].get("project", "istio-system"))

    with istio_project.context:
        telemetry = Telemetry.create_instance(
            cluster=istio_project,
            name=blame("mesh-default"),
            namespace=testconfig["service_protection"]["gateway"].get("project", "istio-system"),
        )

        telemetry.set_tracing(providers=[{"name": "jaeger-otlp"}], random_sampling_percentage=100)

        request.addfinalizer(telemetry.delete)
        telemetry.commit()

    return telemetry


@pytest.fixture(scope="module", autouse=True)
def enable_observability(kuadrant, request, tracing):
    """
    Enable Kuadrant observability with tracing and custom request ID tracking.
    Registers a finalizer to disable observability after tests.
    """

    def _reset():
        kuadrant.set_observability(False)

    request.addfinalizer(_reset)

    observability = ObservabilityOptions(
        enable=True,
        tracing=ObservabilityTracingOptions(defaultEndpoint=tracing.collector_url, insecure=tracing.insecure),
        dataPlane=DataPlaneOptions(
            defaultLevels=[DataPlaneDefaultLevels(debug="true")], httpHeaderIdentifier="x-kuadrant-request-id"
        ),
    )
    kuadrant.set_observability(observability)
    kuadrant.wait_for_ready()
