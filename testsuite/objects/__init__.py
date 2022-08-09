"""Module containing base classes for common objects"""
import abc


class LifecycleObject(abc.ABC):
    """Any objects which has its lifecycle controlled by create() and delete() methods"""

    @abc.abstractmethod
    def commit(self):
        """Commits resource.
        if there is some reconciliation needed, the method should wait until it is all reconciled"""

    @abc.abstractmethod
    def delete(self):
        """Removes resource,
        if there is some reconciliation needed, the method should wait until it is all reconciled"""


class Authorino(LifecycleObject):
    """Authorino instance"""

    @abc.abstractmethod
    def wait_for_ready(self):
        """True, if after some waiting the Authorino is ready"""

    @property
    @abc.abstractmethod
    def authorization_url(self):
        """Authorization URL that can be plugged into envoy"""


class Authorization(LifecycleObject):
    """Object containing Authorization rules and configuration for either Authorino or Kuadrant"""

    @abc.abstractmethod
    def add_oidc_identity(self, name, endpoint):
        """Adds OIDC identity provider"""

    @abc.abstractmethod
    def add_api_key_identity(self, name, label):
        """Adds API Key identity"""

    @abc.abstractmethod
    def remove_all_identities(self):
        """Removes all identities from AuthConfig"""

    @abc.abstractmethod
    def add_host(self, hostname):
        """Adds host"""

    @abc.abstractmethod
    def remove_host(self, hostname):
        """Remove host"""

    @abc.abstractmethod
    def remove_all_hosts(self):
        """Remove host"""

    @abc.abstractmethod
    def wait_for_hosts(self):
        """Waits until all hosts are reconciled"""


class PreexistingAuthorino(Authorino):
    """Authorino which is already deployed prior to the testrun"""

    def __init__(self, authorization_url) -> None:
        super().__init__()
        self._authorization_url = authorization_url

    def wait_for_ready(self):
        return True

    @property
    def authorization_url(self):
        return self._authorization_url

    def commit(self):
        return

    def delete(self):
        return
