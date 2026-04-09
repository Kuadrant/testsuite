---
paths:
  - "testsuite/kuadrant/**/*.py"
  - "testsuite/tests/**/*.py"
---

# Kuadrant Policy Objects

## Policy Hierarchy

```
KubernetesObject
  └─ Policy (testsuite/kuadrant/policy/__init__.py)
      ├─ AuthPolicy (testsuite/kuadrant/policy/authorization/auth_policy.py)
      ├─ RateLimitPolicy (testsuite/kuadrant/policy/rate_limit.py)
      ├─ TLSPolicy (testsuite/kuadrant/policy/tls.py)
      └─ DNSPolicy (testsuite/kuadrant/policy/dns.py)
```

## Policy Lifecycle

1. **Create instance**: `Policy.create_instance(cluster, name, target_ref)`
2. **Configure**: Call methods to add rules, conditions, etc.
3. **Commit**: `policy.commit()` applies to Kubernetes
4. **Wait for ready**: `policy.wait_for_ready()` waits for observedGeneration and Enforced conditions
5. **Delete**: `policy.delete()` (usually via `request.addfinalizer`)

## AuthPolicy Structure (Dot Notation)

AuthPolicy uses a section-based dot notation for configuration. Each section (`identity`, `authorization`, `metadata`, `responses`) is accessed as a property:

```python
@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """Add OIDC identity and OPA authorization"""
    authorization.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    authorization.identity.add_api_key("api-key", selector)
    authorization.identity.add_anonymous("anon")
    authorization.authorization.add_opa_policy("opa", inline_rego)
    authorization.authorization.add_auth_rules("rules", [Rule(...)])
    authorization.metadata.add_http("ext", endpoint, "GET")
    authorization.responses.add_success_header("header", JsonResponse({...}))
    return authorization
```

## RateLimitPolicy Structure

```python
from testsuite.kuadrant.policy.rate_limit import Limit, RateLimitPolicy
from testsuite.kuadrant.policy import CelPredicate, CelExpression

@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add rate limits with conditions"""
    rate_limit.add_limit("basic", [Limit(5, "10s")])
    rate_limit.add_limit(
        "conditional",
        [Limit(2, "10s")],
        when=[CelPredicate("request.path == '/get'")],
        counters=[CelExpression("auth.identity.userid")],
    )
    return rate_limit
```

## Defaults and Overrides

Both AuthPolicy and RateLimitPolicy support `defaults` and `overrides` sections via property chaining. The `.defaults` or `.overrides` property sets the target section, then subsequent method calls apply to that section:

```python
@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """AuthPolicy with defaults and overrides"""
    authorization.defaults.identity.add_oidc("default", oidc_provider.well_known["issuer"])
    authorization.overrides.authorization.add_auth_rules("rules", [...])
    authorization.defaults.strategy(Strategy.MERGE)
    return authorization

@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """RateLimitPolicy with defaults and overrides"""
    rate_limit.defaults.add_limit("default", [Limit(10, "10s")])
    rate_limit.overrides.add_limit("override", [Limit(5, "10s")])
    rate_limit.defaults.strategy(Strategy.ATOMIC)
    return rate_limit
```

## common_features Keyword Arguments

Every section method (identity, authorization, metadata, response) accepts `**common_features` kwargs that add cross-cutting concerns:

```python
from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.authorization import Cache, ValueFrom

@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """AuthPolicy with common_features examples"""
    issuer = oidc_provider.well_known["issuer"]
    # when: Conditional execution via CEL predicates
    authorization.identity.add_oidc("oidc", issuer,
        when=[CelPredicate("request.path.startsWith('/api')")])
    # metrics: Enable metrics collection for this section
    authorization.identity.add_oidc("oidc-metrics", issuer, metrics=True)
    # cache: Cache results with TTL
    authorization.metadata.add_http("ext", url, "GET",
        cache=Cache(ttl=300, key=ValueFrom("context.request.http.path")))
    # priority: Execution priority (higher = executes first)
    authorization.identity.add_oidc("primary", issuer, priority=1)
    authorization.identity.add_api_key("fallback", selector, priority=0)
    return authorization
```

## CelPredicate and When Conditions

CEL predicates are used for conditional policy execution:

```python
from testsuite.kuadrant.policy import CelPredicate, CelExpression
from testsuite.kuadrant.policy.rate_limit import Limit

@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add conditional rate limits with CEL predicates"""
    # Single when condition
    rate_limit.add_limit(
        "path_limit",
        [Limit(2, "10s")],
        when=[CelPredicate("request.path == '/get'")],
    )
    # Multiple when conditions (ANDed together) with per-user counters
    rate_limit.add_limit(
        "user_limit",
        [Limit(50, "30s")],
        when=[
            CelPredicate('request.path == "/v1/chat/completions"'),
            CelPredicate('auth.identity.groups.split(",").exists(g, g == "free")'),
        ],
        counters=[CelExpression("auth.identity.userid")],
    )
    return rate_limit

@pytest.fixture(scope="module")
def authorization(authorization):
    """Add top-level when rule to skip entire AuthPolicy for public paths"""
    authorization.add_rule([CelPredicate("request.path.startsWith('/public')")])
    return authorization
```