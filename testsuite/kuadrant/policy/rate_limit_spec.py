"""
Spec classes for RateLimitPolicy that mirror the Kuadrant operator Go API structure.

This module provides a three-layer structure:
- RateLimitPolicySpec: Top-level spec with defaults/overrides properties
- MergeableRateLimitPolicySpec: Wrapper for defaults/overrides sections
- RateLimitPolicySpecProper: Actual policy rules (limits)

The structure matches the Go implementation in:
github.com/kuadrant/kuadrant-operator/api/v1/ratelimitpolicy_types.go
"""

from typing import Iterable, Optional, TYPE_CHECKING

from testsuite.kuadrant.policy import CelPredicate, CelExpression, Strategy
from testsuite.utils import asdict

if TYPE_CHECKING:
    from testsuite.kuadrant.policy.rate_limit import Limit


class RateLimitPolicySpecProper:
    """
    Actual policy rules matching Go RateLimitPolicySpecProper.

    Contains the limits dict and methods to manipulate it.
    This is the "proper" spec that contains the actual policy configuration.
    """

    def __init__(self):
        self.limits: dict[str, dict] = {}

    def add_limit(
        self,
        name: str,
        limits: Iterable["Limit"],
        when: Optional[list[CelPredicate]] = None,
        counters: Optional[list[CelExpression]] = None,
    ):
        """
        Add a limit to this spec.

        Args:
            name: Name of the limit
            limits: List of Limit objects
            when: Optional CEL predicates for conditional limits
            counters: Optional CEL expressions for custom counters
        """
        limit: dict = {
            "rates": [asdict(limit) for limit in limits],
        }
        if when:
            limit["when"] = [asdict(rule) for rule in when]
        if counters:
            limit["counters"] = [asdict(rule) for rule in counters]

        self.limits[name] = limit

    def to_dict(self) -> dict:
        """Convert to dict for serialization to model.spec"""
        result = {}
        if self.limits:
            result["limits"] = self.limits
        return result


class MergeableRateLimitPolicySpec:
    """
    Wrapper for defaults/overrides sections matching Go MergeableRateLimitPolicySpec.

    Contains a strategy field and embeds a RateLimitPolicySpecProper.
    """

    def __init__(self, strategy: Strategy = Strategy.ATOMIC):
        self._strategy = strategy
        self.proper = RateLimitPolicySpecProper()

    @property
    def strategy(self) -> Strategy:
        """Get the merge strategy."""
        return self._strategy

    @strategy.setter
    def strategy(self, value: Strategy):
        """Set the merge strategy."""
        self._strategy = value

    def add_limit(
        self,
        name: str,
        limits: Iterable["Limit"],
        when: Optional[list[CelPredicate]] = None,
        counters: Optional[list[CelExpression]] = None,
    ):
        """
        Convenience method to add a limit directly (delegates to proper).

        Args:
            name: Name of the limit
            limits: List of Limit objects
            when: Optional CEL predicates for conditional limits
            counters: Optional CEL expressions for custom counters
        """
        self.proper.add_limit(name, limits, when, counters)

    def to_dict(self) -> dict:
        """Convert to dict for serialization to model.spec"""
        result = {"strategy": self._strategy.value}
        result.update(self.proper.to_dict())
        return result


class RateLimitPolicySpec:
    """
    Top-level spec matching Go RateLimitPolicySpec.

    Provides defaults, overrides, and implicit (bare) configuration.
    The proper() method abstracts which section is active.
    """

    def __init__(self, target_ref: dict):
        self.target_ref = target_ref
        self._defaults: Optional[MergeableRateLimitPolicySpec] = None
        self._overrides: Optional[MergeableRateLimitPolicySpec] = None
        self._implicit = RateLimitPolicySpecProper()

    @property
    def defaults(self) -> Optional[MergeableRateLimitPolicySpec]:
        """Returns the defaults section if set, None otherwise."""
        return self._defaults

    @defaults.setter
    def defaults(self, value: Optional[MergeableRateLimitPolicySpec]):
        """Set defaults and clear overrides (mutual exclusivity)."""
        if value is not None:
            self._overrides = None
        self._defaults = value

    @property
    def overrides(self) -> Optional[MergeableRateLimitPolicySpec]:
        """Returns the overrides section if set, None otherwise."""
        return self._overrides

    @overrides.setter
    def overrides(self, value: Optional[MergeableRateLimitPolicySpec]):
        """Set overrides and clear defaults (mutual exclusivity)."""
        if value is not None:
            self._defaults = None
        self._overrides = value

    def proper(self) -> RateLimitPolicySpecProper:
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

        Returns a dict with targetRef and either defaults, overrides, or implicit limits.
        """
        result = {"targetRef": self.target_ref}

        if self._defaults is not None:
            result["defaults"] = self._defaults.to_dict()
        elif self._overrides is not None:
            result["overrides"] = self._overrides.to_dict()
        else:
            # Implicit mode - merge limits directly into spec
            result.update(self._implicit.to_dict())

        return result
