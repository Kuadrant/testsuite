#!/usr/bin/env python3
"""
Unit test demonstrating the bug we fixed - NO Kubernetes connection needed!

THE BUG WE FIXED:
-----------------
BEFORE: Accessing `.defaults` property would immediately call:
    self.model.spec.setdefault("defaults", {})
This creates an empty defaults: {} dict in the spec.

AFTER: Accessing `.defaults` property just returns a context object.
The dict is only created when you actually add something to it.

WHY IT MATTERS:
---------------
Kuadrant validation rejects policies that have both:
  - Empty defaults: {} (explicit defaults section)
  - Top-level limits: {} (implicit defaults)

Error message: "Implicit and explicit defaults are mutually exclusive"
"""

from testsuite.kuadrant.policy.rate_limit import RateLimitPolicy, RateLimitSectionContext
from testsuite.kuadrant.policy.authorization.auth_policy import AuthPolicy, AuthPolicySectionContext


def test_property_returns_context_not_dict():
    """
    THE FIX: .defaults returns a context object, not self with modified spec.
    """
    model = {
        "apiVersion": "kuadrant.io/v1",
        "kind": "RateLimitPolicy",
        "metadata": {"name": "test", "namespace": "test"},
        "spec": {"targetRef": {"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": "test"}},
    }
    policy = RateLimitPolicy(model, context=None)

    # Access .defaults property
    defaults_ctx = policy.defaults

    # Should return a RateLimitSectionContext, not the policy itself
    assert isinstance(defaults_ctx, RateLimitSectionContext), (
        f"Expected RateLimitSectionContext, got {type(defaults_ctx)}"
    )

    # Context should know its section name
    assert defaults_ctx._section_name == "defaults", "Context should know it's for defaults section"

    # CRITICAL: The spec should NOT have created defaults: {} yet
    assert "defaults" not in policy.model.spec, (
        "❌ BUG! Just accessing .defaults created empty defaults: {} in spec!\n"
        "This would cause Kuadrant to reject the policy if you also add top-level limits."
    )

    print("✅ Property returns context object, not dict")
    print(f"   Context type: {type(defaults_ctx).__name__}")
    print(f"   Spec keys: {list(policy.model.spec.keys())}")
    print(f"   ✓ No 'defaults' key created")


def test_multiple_accesses_no_side_effects():
    """
    Accessing properties multiple times should have no side effects.
    """
    model = {
        "apiVersion": "kuadrant.io/v1",
        "kind": "RateLimitPolicy",
        "metadata": {"name": "test", "namespace": "test"},
        "spec": {"targetRef": {"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": "test"}},
    }
    policy = RateLimitPolicy(model, context=None)

    # Access both properties multiple times
    for _ in range(5):
        _ = policy.defaults
        _ = policy.overrides

    # Nothing should be in the spec
    assert "defaults" not in policy.model.spec, "defaults should not exist"
    assert "overrides" not in policy.model.spec, "overrides should not exist"
    assert list(policy.model.spec.keys()) == ["targetRef"], (
        f"Spec should only have targetRef, got: {list(policy.model.spec.keys())}"
    )

    print("✅ Multiple accesses have no side effects")
    print(f"   Accessed .defaults and .overrides 5 times each")
    print(f"   Spec still clean: {list(policy.model.spec.keys())}")


def test_auth_policy_same_fix():
    """
    AuthPolicy had the same bug - test it's fixed there too.
    """
    model = {
        "apiVersion": "kuadrant.io/v1",
        "kind": "AuthPolicy",
        "metadata": {"name": "test", "namespace": "test"},
        "spec": {"targetRef": {"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": "test"}},
    }
    policy = AuthPolicy(model, context=None)

    # Access .defaults
    defaults_ctx = policy.defaults

    # Should return context
    assert isinstance(defaults_ctx, AuthPolicySectionContext), (
        f"Expected AuthPolicySectionContext, got {type(defaults_ctx)}"
    )

    # Should NOT create empty dict
    assert "defaults" not in policy.model.spec, (
        "❌ BUG in AuthPolicy! Accessing .defaults created empty defaults: {} in spec!"
    )

    print("✅ AuthPolicy fix works too")
    print(f"   Context type: {type(defaults_ctx).__name__}")
    print(f"   Spec keys: {list(policy.model.spec.keys())}")


def test_context_knows_its_section():
    """
    The context object carries the section information - no state on policy.
    """
    model = {
        "apiVersion": "kuadrant.io/v1",
        "kind": "RateLimitPolicy",
        "metadata": {"name": "test", "namespace": "test"},
        "spec": {"targetRef": {"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": "test"}},
    }
    policy = RateLimitPolicy(model, context=None)

    defaults_ctx = policy.defaults
    overrides_ctx = policy.overrides

    # Each context knows its section
    assert defaults_ctx._section_name == "defaults"
    assert overrides_ctx._section_name == "overrides"

    # Each context has reference to the policy
    assert defaults_ctx._policy is policy
    assert overrides_ctx._policy is policy

    # Policy has NO state tracking (no spec_section attribute)
    assert not hasattr(policy, "spec_section"), (
        "Policy should NOT have spec_section state tracking! "
        "This was the old approach that we removed."
    )

    print("✅ Context objects carry section info, policy has no state")
    print(f"   defaults context knows: section_name='{defaults_ctx._section_name}'")
    print(f"   overrides context knows: section_name='{overrides_ctx._section_name}'")
    print(f"   ✓ Policy has no spec_section attribute")


def test_what_the_bug_would_have_caused():
    """
    Demonstrate what would have happened with the bug.

    This test shows the YAML that would be generated before the fix,
    and why Kuadrant would reject it.
    """
    print("✅ Understanding the bug:")
    print()
    print("   BUGGY YAML (what would have been generated BEFORE the fix):")
    print("   ---")
    print("   spec:")
    print("     targetRef: {...}")
    print("     defaults: {}      # ← Empty! Created by accessing .defaults")
    print("     limits:           # ← Implicit defaults")
    print("       basic: {...}")
    print()
    print("   KUADRANT VALIDATION ERROR:")
    print("   'Implicit and explicit defaults are mutually exclusive'")
    print()
    print("   FIXED YAML (what we generate NOW):")
    print("   ---")
    print("   spec:")
    print("     targetRef: {...}")
    print("     limits:           # ← Only this, no empty defaults: {}")
    print("       basic: {...}")
    print()
    print("   ✓ Validation passes!")


if __name__ == "__main__":
    print("=" * 80)
    print("UNIT TEST: Empty defaults/overrides bug fix")
    print("=" * 80)
    print()

    try:
        test_property_returns_context_not_dict()
        print()
        test_multiple_accesses_no_side_effects()
        print()
        test_auth_policy_same_fix()
        print()
        test_context_knows_its_section()
        print()
        test_what_the_bug_would_have_caused()

        print()
        print("=" * 80)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 80)
        print()
        print("SUMMARY:")
        print("  ✅ .defaults/.overrides return context objects (not self)")
        print("  ✅ No empty dicts created in spec when accessing properties")
        print("  ✅ Context objects carry section info (no state on policy)")
        print("  ✅ Fix works for both RateLimitPolicy and AuthPolicy")
        print()
        print("THE FIX:")
        print("  Before: @property def defaults(self):")
        print("            self.spec_section = self.model.spec.setdefault('defaults', {})")
        print("            return self")
        print()
        print("  After:  @property def defaults(self):")
        print("            return RateLimitSectionContext(self, 'defaults')")
        print()

    except AssertionError as e:
        print()
        print("=" * 80)
        print("❌ TEST FAILED!")
        print("=" * 80)
        print()
        print(f"Error: {e}")
        print()
        exit(1)
