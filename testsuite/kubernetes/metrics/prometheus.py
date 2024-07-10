"""Simple client for the Prometheus metrics"""

from datetime import datetime, timezone
from typing import Callable

import backoff
from apyproxy import ApyProxy
from httpx import Client

from .service_monitor import ServiceMonitor


def _params(key: str = "", labels: dict[str, str] = None) -> dict[str, str]:
    """Generate metrics query parameters based on key and labels"""
    if not labels:
        return {"query": key}
    # pylint: disable=consider-using-f-string
    return {"query": "%s{%s}" % (key, ",".join(f"{k}='{v}'" for k, v in labels.items()))}


class Metrics:
    """Interface to the returned Prometheus metrics"""

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
    """Interface to the Prometheus client"""

    def __init__(self, client: Client, namespace: str = None):
        self.namespace = namespace
        self.client = ApyProxy(str(client.base_url), session=client).api.v1

    def get_active_targets(self) -> dict:
        """Get active metric targets information"""
        response = self.client.targets.get(params={"state": "active"})

        return response.json()["data"]["activeTargets"]

    def get_metrics(self, key: str = "", labels: dict[str, str] = None) -> Metrics:
        """Get metrics by key or labels"""
        if self.namespace:
            labels = labels or {}
            labels.setdefault("namespace", self.namespace)

        params = _params(key, labels)
        response = self.client.query.get(params=params)

        return Metrics(response.json()["data"]["result"])

    @backoff.on_predicate(backoff.constant, interval=10, jitter=None, max_tries=35)
    def is_reconciled(self, service_monitor: ServiceMonitor):
        """True, if all endpoints in ServiceMonitor are active targets"""
        scrape_pools = set(target["scrapePool"] for target in self.get_active_targets())
        endpoints = len(service_monitor.model.spec.endpoints)
        for i in range(endpoints):
            if f"serviceMonitor/{service_monitor.namespace()}/{service_monitor.name()}/{i}" not in scrape_pools:
                return False

        return True

    def wait_for_scrape(self, service_monitor: ServiceMonitor, metrics_path: str):
        """Wait before next metrics scrape on service is finished"""
        call_time = datetime.now(timezone.utc)

        @backoff.on_predicate(backoff.constant, interval=10, jitter=None, max_tries=4)
        def _wait_for_scrape():
            """Wait for new scrape after the function call time"""
            for target in self.get_active_targets():
                if (
                    f"serviceMonitor/{service_monitor.namespace()}/{service_monitor.name()}" in target["scrapePool"]
                    and metrics_path in target["scrapeUrl"]
                ):
                    return call_time < datetime.fromisoformat(target["lastScrape"][:26]).replace(tzinfo=timezone.utc)
            return False

        assert _wait_for_scrape(), "Scrape wasn't done in time"
