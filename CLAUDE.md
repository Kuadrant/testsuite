# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains the end-to-end test suite for the Kuadrant project (https://kuadrant.io/). The test suite validates Kuadrant components, including Authorino for authorization, Limitador for rate limiting, and DNS and TLS policy features.

## Common CLI Commands

### Environment Setup
```bash
# Install dependencies with poetry (includes dev dependencies)
make poetry

# Install dependencies without dev tools (used in CI/container)
make poetry-no-dev
```

### Running Tests
```bash
make test                # Run all tests (equivalent to 'make kuadrant')
make kuadrant            # Run all Kuadrant tests (excludes standalone_only, multicluster, disruptive)
make authorino           # Run only authorino-related tests
make authorino-standalone # Run tests compatible with standalone Authorino (no Kuadrant required)
make limitador           # Run only Limitador-related tests
make multicluster        # Run multicluster tests
make dnstls              # Run DNS and TLS policy tests
make disruptive          # Run disruptive tests (runs sequentially, not in parallel)
make kuadrant-only       # Run tests that require full Kuadrant (not standalone)
```

### Running Specific Tests
```bash
make testsuite/tests/path/to/test.py                    # Run specific test file
make testsuite/tests/singlecluster/authorino/           # Run all tests in directory
pytest testsuite/tests/path/to/test.py::test_function   # Run specific test function (via poetry run)
```

### Linting and Formatting
```bash
make commit-acceptance   # Run all pre-commit checks (black, pylint, mypy)
make black               # Check code formatting
make reformat            # Reformat code with black
make pylint              # Run pylint
make mypy                # Run type checking
```

### Cleanup
```bash
make clean               # Delete all test-created resources (uses USER env var)
```

## Configuration

Template with all configuration options: `config/settings.local.yaml.tpl`

## Test Suite Structure

### Test Modules

**testsuite/tests/singlecluster/**: Single-cluster test scenarios
- `authorino/`: Authorino-specific features (identity verification, metadata, authorization, response manipulation)
- `limitador/`: Rate limiting tests
- `gateway/`: Gateway API behavior tests
- `observability/`: Metrics and monitoring tests
- `reconciliation/`: Resource reconciliation tests
- `defaults/`: Default policy behavior
- `overrides/`: Policy override behavior
- `identical_hostnames/`: Multi-gateway hostname conflict tests

**testsuite/tests/multicluster/**: Multi-cluster test scenarios
- `coredns/`: CoreDNS integration tests
- `load_balanced/`: Load balancing across clusters

### Pytest Markers

Tests use markers to categorize functionality. All available markers are defined in `pyproject.toml` under `[tool.pytest.ini_options]`.

### Customizing Fixtures

Tests commonly override fixtures to customize behavior:

```python
import pytest
from testsuite.kuadrant.policy.rate_limit import Limit

@pytest.fixture(scope="module")
def authorization(authorization, oidc_provider):
    """Customize authorization by adding identity providers"""
    authorization.identity.add_oidc("oidc", oidc_provider.well_known["issuer"])
    authorization.identity.add_api_key("api_key")
    return authorization

@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add limits to rate limit policy"""
    rate_limit.add_limit("basic", [Limit(5, "10s")])
    return rate_limit

@pytest.fixture(scope="module", autouse=True)
def commit(request, authorization, rate_limit):
    """Automatically commit policies before tests run"""
    for component in [authorization, rate_limit]:
        if component is not None:
            request.addfinalizer(component.delete)
            component.commit()
            component.wait_for_ready()
```

The `commit` fixture with `autouse=True` automatically runs before tests, ensuring policies are created and ready. The `request.addfinalizer` ensures cleanup after tests complete.

### Policy Lifecycle

The Kuadrant policy fixture setups follow this pattern:

1. **Create instance**: `Policy.create_instance(cluster, name, target_ref)`
2. **Configure**: Call methods to add rules, conditions, etc.
3. **Commit**: `policy.commit()` applies to Kubernetes
4. **Wait for ready**: `policy.wait_for_ready()` waits for observedGeneration and Enforced conditions
5. **Delete**: `policy.delete()` (usually via finalizer)
