"""Utilities for querying Envoy metrics to verify policy application in the data plane."""

import time


def get_kuadrant_configs_value(metrics_route):
    """Get the current value of kuadrant_configs metric.

    Args:
        metrics_route: OpenShift Route to metrics service

    Returns:
        Integer value of kuadrant_configs metric, or 0 if not found
    """
    if metrics_route is None:
        return 0

    try:
        metrics_client = metrics_route.client()
        response = metrics_client.get("/stats/prometheus")
        if response.status_code == 200:
            # Parse the metric value from lines like: kuadrant_configs{} 1
            for line in response.text.split("\n"):
                if line.startswith("kuadrant_configs{}"):
                    return int(line.split()[1])
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return 0


def wait_for_policy_applied_to_envoy(metrics_route, initial_value, timeout=120, interval=5):
    """Wait for policy to be applied in Envoy by checking for kuadrant_configs metric change.

    Uses metrics OpenShift Route which bypasses Gateway and policy enforcement.

    Args:
        metrics_route: OpenShift Route to metrics service
        initial_value: Initial value of kuadrant_configs before policy was committed
        timeout: Maximum time to wait in seconds (default: 120)
        interval: Polling interval in seconds (default: 5)

    Returns:
        True if policy is applied (kuadrant_configs increased), False if timeout reached
    """
    if metrics_route is None:
        # No metrics route available (e.g., standalone mode), skip waiting
        return True

    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            current_value = get_kuadrant_configs_value(metrics_route)
            # Check if metric exists and has increased from initial value
            if current_value is not None and current_value > (initial_value or 0):
                return True
        except Exception:  # pylint: disable=broad-exception-caught
            pass  # Ignore connection errors and continue polling

        time.sleep(interval)

    return False
