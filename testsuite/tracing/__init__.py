"""Module with Abstract Tracing client for traces management"""

import abc


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
    def get_trace(self, request_id: str, service: str, tag_name: str, tags: dict = None) -> list:
        """Search traces in tracing client by service name and tag."""
