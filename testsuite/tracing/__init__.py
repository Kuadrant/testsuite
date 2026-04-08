"""Module with Abstract Tracing client for traces management"""

import abc
from typing import Any, Optional


class TracingClient(abc.ABC):
    """Tracing client for traces management"""

    @property
    @abc.abstractmethod
    def insecure(self):
        """Returns True, if the connection to the client is insecure"""

    @property
    @abc.abstractmethod
    def query_url(self):
        """Returns URL for clients to query"""

    @property
    @abc.abstractmethod
    def collector_url(self):
        """Returns URL for application to deposit traces"""

    @abc.abstractmethod
    def get_traces(
        self,
        service: str,
        tags: Optional[dict[str, str]] = None,
        min_processes: int = 0,
        start_time: Optional[int] = None,
    ) -> list[Any]:
        """Search traces in tracing client by service name and tags.
        If min_processes is set, retries until at least that many service processes are present.
        If start_time is set, only returns traces that started after that time (in microseconds)."""
