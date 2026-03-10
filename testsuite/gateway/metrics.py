"""Gateway metrics querying functionality"""

import re
import backoff
import httpx


class GatewayMetrics:
    """
    Handles querying metrics from a Gateway via OpenShift Route or LoadBalancer Service.
    """

    def __init__(self, metrics_route, metrics_service=None):
        """
        Initialize GatewayMetrics with metrics route or service.

        Args:
            metrics_route: The OpenshiftRoute object (OpenShift) or None (Kind)
            metrics_service: The Service object (for LoadBalancer on Kind/Kubernetes)
        """
        self.metrics_route = metrics_route
        self.metrics_service = metrics_service

    @backoff.on_exception(
        backoff.constant,
        (httpx.HTTPError, httpx.TimeoutException),
        max_tries=3,
        interval=2,
        jitter=None,
    )
    def get_kuadrant_configs(self):
        """
        Queries and returns the kuadrant_configs metric value from the gateway.
        This metric represents the total number of configs loaded in the wasm shim.

        Returns:
            int: The metric value, or 0 if metric not found or route unavailable
        """
        if self.metrics_route is not None:
            # OpenShift: Use Route
            metrics_url = f"http://{self.metrics_route.hostname}/stats/prometheus"
        elif self.metrics_service is not None:
            # Kind/Kubernetes: Use LoadBalancer service
            # Get the external IP from the service status
            service_model = self.metrics_service.refresh().model
            if hasattr(service_model.status, 'loadBalancer') and service_model.status.loadBalancer.ingress:
                ingress = service_model.status.loadBalancer.ingress[0]
                # Could be either 'ip' or 'hostname' depending on the platform
                external_address = getattr(ingress, 'ip', None) or getattr(ingress, 'hostname', None)
                if external_address:
                    metrics_url = f"http://{external_address}:15020/stats/prometheus"
                else:
                    return 0
            else:
                return 0
        else:
            return 0

        # Query the metrics endpoint
        response = httpx.get(metrics_url, timeout=5.0)
        response.raise_for_status()

        # Parse kuadrant_configs metric using regex
        # Format: kuadrant_configs{} 4
        pattern = r"^kuadrant_configs.*?\s+(\d+)"
        for line in response.text.split("\n"):
            match = re.match(pattern, line)
            if match:
                return int(match.group(1))

        return 0

    def wait_for_kuadrant_config_increase(self, initial_value):
        """
        Polls the kuadrant_configs metric until it increases from the initial value.

        Args:
            initial_value: The initial metric value to compare against

        Returns:
            float: The final metric value after increase
        """

        @backoff.on_predicate(
            backoff.constant,
            lambda x: x is None or x <= initial_value,
            max_tries=5,
            interval=2,
            jitter=None,
        )
        def poll_metric():
            return self.get_kuadrant_configs()

        final_value = poll_metric()

        if final_value is None or final_value < initial_value:
            raise AssertionError(
                f"kuadrant_configs metric decreased. Initial: {initial_value}, Final: {final_value}"
            )

        return final_value
