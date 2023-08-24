"""Module containing all Gateway API related classes"""
from abc import ABC, abstractmethod


class Referencable(ABC):
    """Object that can be referenced in Gateway API style"""

    @property
    @abstractmethod
    def reference(self) -> dict[str, str]:
        """
        Returns dict, which can be used as reference in Gateway API Objects.
        https://gateway-api.sigs.k8s.io/references/spec/#gateway.networking.k8s.io/v1beta1.ParentReference
        """
