"""Factory for creating GatewayMetrics instances based on exposer type."""


from testsuite.config import settings
from testsuite.gateway import Exposer, Gateway
from testsuite.gateway.metrics import GatewayMetrics


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
    # Import here to avoid circular imports
    from testsuite.gateway.exposers import OpenShiftExposer, LoadBalancerServiceExposer
    from testsuite.gateway.metrics import OpenShiftGatewayMetrics, LoadBalancerGatewayMetrics
    from testsuite.kubernetes.service import Service, ServicePort

    if isinstance(exposer, OpenShiftExposer):
        # OpenShift: Create ClusterIP Service + Route
        from testsuite.kubernetes.openshift.route import OpenshiftRoute

        metrics_service = Service.create_instance(
            gateway.cluster,
            gateway.metrics_service_name,
            selector={"gateway.networking.k8s.io/gateway-name": gateway.name()},
            ports=[ServicePort(name="metrics", port=15020, targetPort=15020)],
            labels=gateway.model.metadata.get("labels", {}),
            service_type="ClusterIP",
        )
        metrics_service.commit()

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
        metrics_service = Service.create_instance(
            gateway.cluster,
            gateway.metrics_service_name,
            selector={"gateway.networking.k8s.io/gateway-name": gateway.name()},
            ports=[ServicePort(name="metrics", port=15020, targetPort=15020)],
            labels=gateway.model.metadata.get("labels", {}),
            service_type="LoadBalancer",
        )
        metrics_service.commit()
        metrics_service.wait_for_ready(slow_loadbalancers=settings["control_plane"]["slow_loadbalancers"])

        return LoadBalancerGatewayMetrics(gateway, metrics_service)

    else:
        # For other exposers (DNSPolicyExposer, etc.), metrics are not supported
        raise NotImplementedError(f"Metrics not supported for exposer type: {type(exposer).__name__}")