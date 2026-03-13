"""Factory for creating GatewayMetrics instances based on exposer type."""


from testsuite.config import settings
from testsuite.gateway import Exposer, Gateway
from testsuite.gateway.metrics import GatewayMetrics
from testsuite.kubernetes.service import Service
from testsuite.gateway.exposers import OpenShiftExposer, LoadBalancerServiceExposer
from testsuite.gateway.metrics import OpenShiftGatewayMetrics, LoadBalancerGatewayMetrics


def _create_metrics_service(gateway: "Gateway", service_type: str) -> Service:
    """
    Helper function to create a metrics service.

    Args:
        gateway: The gateway to create metrics service for
        service_type: Type of service ("ClusterIP" or "LoadBalancer")

    Returns:
        Service: The created metrics service
    """
    from testsuite.kubernetes.service import Service, ServicePort

    metrics_service = Service.create_instance(
        gateway.cluster,
        gateway.metrics_service_name,
        selector={"gateway.networking.k8s.io/gateway-name": gateway.name()},
        ports=[ServicePort(name="metrics", port=15020, targetPort=15020)],
        labels=gateway.model.metadata.get("labels", {}),
        service_type=service_type,
    )
    metrics_service.commit()
    return metrics_service


def create_gateway_metrics(exposer: "Exposer", gateway: "Gateway") -> "GatewayMetrics":
    """
    Factory function to create the appropriate GatewayMetrics implementation
    based on the exposer type.

    Args:
        exposer: The exposer instance used for the gateway
        gateway: The gateway to expose metrics for

    Returns:
        GatewayMetrics: The appropriate metrics implementation
    """
    if isinstance(exposer, OpenShiftExposer):
        # OpenShift: Create ClusterIP Service + Route
        from testsuite.kubernetes.openshift.route import OpenshiftRoute

        metrics_service = _create_metrics_service(gateway, "ClusterIP")

        metrics_route = OpenshiftRoute.create_instance(
            gateway.cluster,
            gateway.metrics_service_name,
            gateway.metrics_service_name,
            target_port="metrics",
            tls=False
        )
        metrics_route.commit()

        return OpenShiftGatewayMetrics(metrics_route, metrics_service)

    elif isinstance(exposer, LoadBalancerServiceExposer):
        # LoadBalancer: Create LoadBalancer Service
        metrics_service = _create_metrics_service(gateway, "LoadBalancer")
        metrics_service.wait_for_ready(slow_loadbalancers=settings["control_plane"]["slow_loadbalancers"])

        return LoadBalancerGatewayMetrics(gateway, metrics_service)

    else:
        # For other exposers (DNSPolicyExposer, etc.), metrics are not supported
        raise NotImplementedError(f"Metrics not supported for exposer type: {type(exposer).__name__}")