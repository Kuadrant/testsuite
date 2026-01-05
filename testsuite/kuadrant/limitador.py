"""Limitador CR object"""

from abc import ABC
from dataclasses import dataclass
from typing import Optional, Literal

from openshift_client import selector

from testsuite.kubernetes import CustomResource, modify
from testsuite.kubernetes.deployment import Deployment
from testsuite.utils import asdict


@dataclass
class TracingOptions:
    """Dataclass containing limitador tracing specification"""

    endpoint: str


@dataclass
class ABCStorage(ABC):
    """
    Abstract storage class
    https://github.com/Kuadrant/limitador-operator/blob/main/doc/storage.md
    """


@dataclass
class Disk(ABCStorage):
    """Disk storage dataclass

    :param storageClassName: 	StorageClass of the storage offered by cluster administrators
                                [default: default storage class of the cluster]
    :param requests:            Minimum volume size [default: 1Gi]
    :param optimize:            'throughput' 	Optimizes for higher throughput. Default
                                'disk' 	        Optimizes for disk usage
    """

    storageClassName: Optional[str] = None  # pylint: disable=invalid-name
    requests: Optional[str] = None
    optimize: Optional[Literal["throughput", "disk"]] = None

    def asdict(self):
        """Custom asdict due to nested structure."""
        dic = {"disk": {"persistentVolumeClaim": {}}}
        if self.storageClassName:
            dic["disk"]["persistentVolumeClaim"]["storageClassName"] = self.storageClassName
        if self.requests:
            dic["disk"]["persistentVolumeClaim"]["resources"] = {"requests": self.requests}
        if self.optimize:
            dic["disk"]["optimize"] = self.optimize
        return dic


@dataclass
class Redis(ABCStorage):
    """
    Redis storage dataclass

    :param configSecretRefName: The secret reference storing the URL for Redis
    """

    configSecretRefName: str  # pylint: disable=invalid-name

    def asdict(self):
        """Custom asdict due to nested structure."""
        return {"redis": {"configSecretRef": {"name": self.configSecretRefName}}}


@dataclass
class RedisCached(Redis):
    """Redis storage dataclass

    :param batch-size:          Size of entries to flush in as single flush [default: 100]
    :param flush-period: 	    Flushing period for counters in milliseconds [default: 1000]
    :param max-cached: 	        Maximum amount of counters cached [default: 10000]
    :param response-timeout: 	Timeout for Redis commands in milliseconds [default: 350]
    """

    batch_size: Optional[int] = None
    flush_period: Optional[int] = None
    max_cached: Optional[int] = None
    response_timeout: Optional[int] = None

    def asdict(self):
        """Custom asdict due to nested structure"""
        dic = {"redis-cached": {"configSecretRef": {"name": self.configSecretRefName}, "options": {}}}
        if self.batch_size:
            dic["redis-cached"]["options"]["batch-size"] = self.batch_size
        if self.flush_period:
            dic["redis-cached"]["options"]["flush-period"] = self.flush_period
        if self.max_cached:
            dic["redis-cached"]["options"]["max-cached"] = self.max_cached
        if self.response_timeout:
            dic["redis-cached"]["options"]["response-timeout"] = self.response_timeout
        return dic


class LimitadorCR(CustomResource):
    """Represents Limitador CR objects"""

    @modify
    def set_storage(self, storage: ABCStorage):
        """Sets external counter storage option"""
        self.model.spec.setdefault("storage", asdict(storage))

    @modify
    def reset_storage(self):
        """Resets external counter storage option back to default in-memory storage"""
        self.model.spec.storage = None

    @modify
    def set_tracing(self, tracing: TracingOptions):
        """Sets tracing configuration"""
        self.model.spec["tracing"] = asdict(tracing)

    @modify
    def reset_tracing(self):
        """Resets tracing configuration"""
        self.model.spec.tracing = None

    @property
    def deployment(self) -> Deployment:
        """Returns Deployment object for this Limitador"""
        with self.context:
            return selector("deployment", labels={"app": self.name()}).object(cls=Deployment)

    @property
    def pod(self):
        """Returns Pod object for this Limitadaor"""
        with self.context:
            return selector("pod", labels={"app": self.name()}).object()
