"""
Mixin providing standardized section access for authorization configurations.

This module eliminates code duplication between AuthConfig and AuthPolicySpecProper
by providing a single source of truth for section management.
"""

from functools import cached_property
from .sections import IdentitySection, AuthorizationSection, MetadataSection, ResponseSection


class SectionManagementMixin:
    """
    Mixin providing standardized section access for authorization configs.

    Provides:
    - identity (IdentitySection) - Authentication configuration
    - authorization (AuthorizationSection) - Authorization rules
    - metadata (MetadataSection) - External metadata enrichment
    - responses (ResponseSection) - Response manipulation

    Subclasses must implement:
    - auth_section property - returns the dict where sections are stored
    - _response_data_key property (optional) - "filters" or "dynamicMetadata"
    """

    @property
    def auth_section(self):
        """Must be implemented by subclass - returns dict for section storage"""
        raise NotImplementedError(f"{self.__class__.__name__} must implement auth_section property")

    @property
    def _response_data_key(self):
        """Override to specify 'filters' or 'dynamicMetadata'. Defaults to 'dynamicMetadata'."""
        return "dynamicMetadata"

    @cached_property
    def identity(self) -> "IdentitySection":
        """Access identity/authentication section"""
        return IdentitySection(self, "authentication")

    @cached_property
    def authorization(self) -> "AuthorizationSection":
        """Access authorization rules section"""
        return AuthorizationSection(self, "authorization")

    @cached_property
    def metadata(self) -> "MetadataSection":
        """Access metadata enrichment section"""
        return MetadataSection(self, "metadata")

    @cached_property
    def responses(self) -> "ResponseSection":
        """Access response manipulation section"""
        return ResponseSection(self, "response", self._response_data_key)
