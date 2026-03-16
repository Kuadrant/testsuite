"""
Spec classes for AuthPolicy that mirror the Kuadrant operator Go API structure.

This module provides a three-layer structure:
- AuthPolicySpec: Top-level spec with defaults/overrides properties
- MergeableAuthPolicySpec: Wrapper for defaults/overrides sections
- AuthPolicySpecProper: Actual policy rules (authentication, authorization, etc.)

The structure matches the Go implementation in:
github.com/kuadrant/kuadrant-operator/api/v1/authpolicy_types.go
"""

from functools import cached_property
from typing import Optional

from testsuite.kuadrant.policy import Strategy
from testsuite.kuadrant.policy.authorization.sections import (
    IdentitySection,
    AuthorizationSection,
    MetadataSection,
    ResponseSection,
)


class AuthPolicySpecProper:
    """
    Actual policy rules matching Go AuthPolicySpecProper.

    Contains the auth scheme (rules dict) with sections for:
    - authentication (identity)
    - authorization
    - metadata
    - response

    This is the "proper" spec that contains the actual policy configuration.
    """

    def __init__(self, parent_policy) -> None:
        """
        Initialize the spec proper.

        Args:
            parent_policy: The parent AuthPolicy or builder object that owns this spec.
                          Used by sections to access committed state and modify_and_apply.
        """
        self.parent_policy = parent_policy
        self._rules: dict = {}

    @property
    def rules(self) -> dict:
        """Returns the rules dict (creates it if needed)."""
        return self._rules

    @property
    def auth_section(self):
        """Returns the rules dict where sections are stored."""
        return self._rules

    @cached_property
    def identity(self) -> IdentitySection:
        """Access identity/authentication section"""
        return IdentitySection(self, "authentication")

    @cached_property
    def authorization(self) -> AuthorizationSection:
        """Access authorization rules section"""
        return AuthorizationSection(self, "authorization")

    @cached_property
    def metadata(self) -> MetadataSection:
        """Access metadata enrichment section"""
        return MetadataSection(self, "metadata")

    @cached_property
    def responses(self) -> ResponseSection:
        """Access response manipulation section (Kuadrant uses 'filters')"""
        return ResponseSection(self, "response", "filters")

    @property
    def committed(self):
        """Proxy to parent policy's committed status."""
        return self.parent_policy.committed

    def modify_and_apply(self, modifier_func, retries=2, cmd_args=None):
        """Proxy to parent policy's modify_and_apply."""
        return self.parent_policy.modify_and_apply(modifier_func, retries, cmd_args)

    def to_dict(self) -> dict:
        """Convert to dict for serialization to model.spec."""
        result = {}
        if self._rules:
            result["rules"] = self._rules
        return result


class MergeableAuthPolicySpec:
    """
    Wrapper for defaults/overrides sections matching Go MergeableAuthPolicySpec.

    Contains a strategy field and embeds an AuthPolicySpecProper.
    """

    def __init__(self, parent_policy, strategy: Strategy = Strategy.ATOMIC) -> None:
        """
        Initialize the mergeable spec.

        Args:
            parent_policy: The parent AuthPolicy that owns this spec.
            strategy: The merge strategy (ATOMIC or MERGE).
        """
        self.parent_policy = parent_policy
        self._strategy = strategy
        self.proper = AuthPolicySpecProper(self)

    def strategy(self, value: Strategy):
        """
        Set the merge strategy.

        Args:
            value: The merge strategy (Strategy.ATOMIC or Strategy.MERGE)

        Returns:
            self for chaining
        """
        self._strategy = value
        return self

    @property
    def committed(self):
        """Proxy to parent policy's committed status."""
        return self.parent_policy.committed

    def modify_and_apply(self, modifier_func, retries=2, cmd_args=None):
        """Proxy to parent policy's modify_and_apply."""
        return self.parent_policy.modify_and_apply(modifier_func, retries, cmd_args)

    # Convenience properties to access sections directly
    @property
    def identity(self):
        """Direct access to identity section."""
        return self.proper.identity

    @property
    def authorization(self):
        """Direct access to authorization section."""
        return self.proper.authorization

    @property
    def metadata(self):
        """Direct access to metadata section."""
        return self.proper.metadata

    @property
    def responses(self):
        """Direct access to response section."""
        return self.proper.responses

    def to_dict(self) -> dict:
        """Convert to dict for serialization to model.spec."""
        result = {"strategy": self._strategy.value}
        result.update(self.proper.to_dict())
        return result


class AuthPolicySpec:
    """
    Top-level spec matching Go AuthPolicySpec.

    Provides defaults, overrides, and implicit (bare) configuration.
    The proper() method abstracts which section is active.
    """

    def __init__(self, parent_policy, target_ref: dict) -> None:
        """
        Initialize the spec.

        Args:
            parent_policy: The parent AuthPolicy that owns this spec.
            target_ref: The targetRef dict for the policy.
        """
        self.parent_policy = parent_policy
        self.target_ref = target_ref
        self._defaults: Optional[MergeableAuthPolicySpec] = None
        self._overrides: Optional[MergeableAuthPolicySpec] = None
        self._implicit = AuthPolicySpecProper(parent_policy)

    @property
    def defaults(self) -> Optional[MergeableAuthPolicySpec]:
        """Returns the defaults section if set, None otherwise."""
        return self._defaults

    @defaults.setter
    def defaults(self, value: Optional[MergeableAuthPolicySpec]):
        """Set defaults and clear overrides (mutual exclusivity)."""
        if value is not None:
            self._overrides = None
        self._defaults = value

    @property
    def overrides(self) -> Optional[MergeableAuthPolicySpec]:
        """Returns the overrides section if set, None otherwise."""
        return self._overrides

    @overrides.setter
    def overrides(self, value: Optional[MergeableAuthPolicySpec]):
        """Set overrides and clear defaults (mutual exclusivity)."""
        if value is not None:
            self._defaults = None
        self._overrides = value

    def proper(self) -> AuthPolicySpecProper:
        """
        Returns the active SpecProper (matches Go Proper() method).

        Priority:
        1. defaults (if set)
        2. overrides (if set)
        3. implicit (bare configuration)
        """
        if self._defaults is not None:
            return self._defaults.proper
        if self._overrides is not None:
            return self._overrides.proper
        return self._implicit

    def to_dict(self) -> dict:
        """
        Convert to dict for serialization to model.spec.

        Returns a dict with targetRef and either defaults, overrides, or implicit rules.
        """
        result = {"targetRef": self.target_ref}

        if self._defaults is not None:
            result["defaults"] = self._defaults.to_dict()
        elif self._overrides is not None:
            result["overrides"] = self._overrides.to_dict()
        else:
            # Implicit mode - merge rules directly into spec
            result.update(self._implicit.to_dict())

        return result
