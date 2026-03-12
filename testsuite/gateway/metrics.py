"""Gateway metrics querying functionality"""

import re
from abc import ABC, abstractmethod

import backoff
import httpx


class GatewayMetrics(ABC):
    """
    Base class for querying metrics from a Gateway.
    """

    @property
    @abstractmethod
    def metrics_url(self):
        """Get the metrics endpoint URL"""

    @abstractmethod
    def delete(self):
        """Clean up metrics resources"""

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
            int: The metric value, or 0 if metric not found or endpoint unavailable
        """
        # Query the metrics endpoint with cache-busting
        response = httpx.get(
            self.metrics_url,
            timeout=5.0,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
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
        if final_value is None or final_value <= initial_value:
            raise AssertionError(
                f"kuadrant_configs metric decreased. Initial: {initial_value}, Final: {final_value}"
            )

        return final_value

    def wait_for_kuadrant_config_value(self, expected_value):
        """
        Polls the kuadrant_configs metric until it reaches or exceeds the expected value.

        Args:
            expected_value: The expected metric value to wait for

        Returns:
            int: The final metric value
        """
        @backoff.on_predicate(
            backoff.constant,
            lambda x: x is None or x < expected_value,
            max_tries=10,
            interval=3,
            jitter=None,
        )
        def poll_metric():
            return self.get_kuadrant_configs()

        final_value = poll_metric()
        if final_value is None or final_value < expected_value:
            raise AssertionError(
                f"kuadrant_configs metric did not reach expected value. "
                f"Expected: >={expected_value}, Actual: {final_value}"
            )

        return final_value


class OpenShiftGatewayMetrics(GatewayMetrics):
    """Gateway metrics implementation for OpenShift (ClusterIP + Route)"""

    def __init__(self, metrics_route, metrics_service):
        """
        Initialize OpenShift metrics.

        Args:
            metrics_route: OpenshiftRoute object exposing the metrics
            metrics_service: Service object for metrics endpoint
        """
        self._metrics_route = metrics_route
        self._metrics_service = metrics_service

    @property
    def metrics_url(self):
        """Get the metrics URL from the route"""
        return f"http://{self._metrics_route.hostname}/stats/prometheus"

    def delete(self):
        """Delete the metrics route and service"""
        if self._metrics_route:
            self._metrics_route.delete(ignore_not_found=True)
        if self._metrics_service:
            self._metrics_service.delete(ignore_not_found=True)


class LoadBalancerGatewayMetrics(GatewayMetrics):
    """Gateway metrics implementation for LoadBalancer (LoadBalancer Service)"""

    def __init__(self, gateway, metrics_service):
        """
        Initialize LoadBalancer metrics.

        Args:
            gateway: Gateway object to get external IP from
            metrics_service: Service object for metrics endpoint
        """
        self._gateway = gateway
        self._metrics_service = metrics_service

    @property
    def metrics_url(self):
        """Get the metrics URL from metrics service external IP"""
        return f"http://{self._metrics_service.external_ip}:15020/stats/prometheus"

    def delete(self):
        """Delete the metrics service"""
        if self._metrics_service:
            self._metrics_service.delete(ignore_not_found=True)
