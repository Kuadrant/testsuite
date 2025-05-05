from urllib.parse import urljoin
import httpx


class CustomMetricsApiServerClient(httpx.Client):
    """Client for the Custom Metrics API Server"""

    def __init__(self, url: str):
        return super().__init__(base_url=url, verify=False, headers={"Content-Type": "application/json"})

    def write_metric(self, namespace: str, resource_type: str, name: str, metric: str, value: int):
        """Write a metric value to the Custom Metrics API Server.

        Args:
            namespace: The namespace of the resource
            resource_type: The type of resource (e.g. 'pods', 'services')
            name: The name of the resource
            metric: The name of the metric
            value: The value to set
        """
        endpoint = f"/write-metrics/namespaces/{namespace}/{resource_type}/{name}/{metric}"

        response = self.post(endpoint, content=f"{value}")
        response.raise_for_status()
        return response.status_code
