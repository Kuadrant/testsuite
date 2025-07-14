"""TokenRateLimitPolicy implementation for policy"""

from testsuite.gateway import Referencable
from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy
from testsuite.kubernetes.client import KubernetesClient


class TokenRateLimitPolicy(RateLimitPolicy):
    """TokenRateLimitPolicy object, used for applying token rate limiting rules to a Gateway/HTTPRoute"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spec_section = None

    @classmethod
    def create_instance(
        cls,
        cluster: KubernetesClient,
        name,
        target: Referencable,
        section_name: str = None,
        labels: dict[str, str] = None,
    ):
        """Creates new instance of TokenRateLimitPolicy"""
        model: dict = {
            "apiVersion": "kuadrant.io/v1alpha1",
            "kind": "TokenRateLimitPolicy",
            "metadata": {"name": name, "labels": labels},
        }
        if section_name:
            model["spec"]["targetRef"]["sectionName"] = section_name
        return cls(model, context=cluster.context)
