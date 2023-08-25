"""Simple client for the OpenShift metrics"""
from typing import Callable
from datetime import datetime

import httpx
import backoff
from apyproxy import ApyProxy


def _params(key: str = "", labels: dict[str, str] = None) -> dict[str, str]:
    """Generate metrics query parameters based on key and labels"""
    if not labels:
        return {"query": key}
    # pylint: disable=consider-using-f-string
    return {"query": "%s{%s}" % (key, ",".join(f"{k}='{v}'" for k, v in labels.items()))}


class Metrics:
    """Interface to the returned OpenShift metrics"""

    def __init__(self, metrics):
        self.metrics = metrics

    def filter(self, func: Callable[[dict], bool]) -> "Metrics":
        """Filter method accept function `func` as a single argument.
        Given function will be used as a filter on metrics structure.
        E.g. func = lambda x: x["metric"]["evaluator_name"] == 'json'
        After the filtering, new Metrics object will be returned."""
        return Metrics([m for m in self.metrics if func(m)])

    @property
    def names(self) -> list[str]:
        """Return list of metrics names"""
        return [m["metric"]["__name__"] for m in self.metrics]

    @property
    def values(self) -> list[float]:
        """Return list of metrics values as floats"""
        return [float(m["value"][1]) for m in self.metrics]


class Prometheus:
    """Interface to the OpenShift Prometheus client"""

    def __init__(self, url: str, token: str, namespace: str = None):
        self.token = token
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.namespace = namespace

        self._client = httpx.Client(headers=self.headers, verify=False)
        self.client = ApyProxy(url, self._client).api.v1

    def get_targets(self) -> dict:
        """Get active metric targets information"""
        params = {"state": "active"}
        response = self.client.targets.get(params=params)

        return response.json()["data"]["activeTargets"]

    def get_metrics(self, key: str = "", labels: dict[str, str] = None) -> Metrics:
        """Get metrics by key or labels"""
        if self.namespace:
            labels = labels or {}
            labels.setdefault("namespace", self.namespace)

        params = _params(key, labels)
        response = self.client.query.get(params=params)

        return Metrics(response.json()["data"]["result"])

    def wait_for_scrape(self, target_service: str, metrics_path: str = "/metrics"):
        """Wait before next metrics scrape on service is finished"""
        call_time = datetime.utcnow()

        @backoff.on_predicate(backoff.constant, interval=10, jitter=None, max_tries=10)
        def _wait_for_scrape():
            """Wait for new scrape after the function call time"""
            for target in self.get_targets():
                if (
                    "service" in target["labels"].keys()
                    and target["labels"]["service"] == target_service
                    and target["discoveredLabels"]["__metrics_path__"] == metrics_path
                ):
                    return call_time < datetime.fromisoformat(target["lastScrape"][:26])
            return False

        _wait_for_scrape()

    def close(self):
        """Close httpx client connection"""
        self._client.close()
