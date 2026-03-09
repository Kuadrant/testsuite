"""Gateway metrics querying functionality"""

import re
import backoff
import httpx


class GatewayMetrics:
    """
    Handles querying metrics from a Gateway via OpenShift Route.
    """

    def __init__(self, metrics_route):
        """
        Initialize GatewayMetrics with a metrics route.

        Args:
            metrics_route: The OpenshiftRoute object exposing gateway metrics
        """
        self.metrics_route = metrics_route

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
        if self.metrics_route is None:
            return 0

        # Access metrics via route hostname
        metrics_url = f"http://{self.metrics_route.hostname}/stats/prometheus"

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
