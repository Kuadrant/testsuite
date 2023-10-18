"""Module containing all Gateway API related classes"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from testsuite.objects import asdict


class Referencable(ABC):
    """Object that can be referenced in Gateway API style"""

    @property
    @abstractmethod
    def reference(self) -> dict[str, str]:
        """
        Returns dict, which can be used as reference in Gateway API Objects.
        https://gateway-api.sigs.k8s.io/references/spec/#gateway.networking.k8s.io/v1beta1.ParentReference
        """


@dataclass
class CustomReference(Referencable):
    """
    Manually creates Reference object.
    https://gateway-api.sigs.k8s.io/references/spec/#gateway.networking.k8s.io%2fv1beta1.ParentReference
    """

    @property
    def reference(self) -> dict[str, Any]:
        return asdict(self)

    group: str
    kind: str
    name: str
    namespace: Optional[str] = None
    sectionName: Optional[str] = None  # pylint: disable=invalid-name
    port: Optional[int] = None
