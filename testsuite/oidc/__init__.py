"""Common classes for OIDC provider"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Tuple


@dataclass
class Token:
    """Token class"""
    access_token: str
    refresh_function: Callable[[str], "Token"]
    refresh_token: str

    def refresh(self) -> "Token":
        """Refreshes token"""
        return self.refresh_function(self.refresh_token)

    def __str__(self) -> str:
        return self.access_token


class OIDCProvider(ABC):
    """Interface for all methods we need for OIDCProvider"""

    @property
    @abstractmethod
    def well_known(self):
        """Dict (or a dict-like structure) access to all well_known URLS"""

    @abstractmethod
    def get_token(self, username=None, password=None) -> Token:
        """Returns Token wrapper class with current access token and ability to refresh it"""
