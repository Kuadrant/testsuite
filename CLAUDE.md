# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains the end-to-end test suite for the Kuadrant project - a Kubernetes-native API management solution. The test suite validates Kuadrant Service Protection capabilities including Authorino (authorization), Limitador (rate limiting), DNSPolicy, and TLSPolicy functionality.

## Build and Test Commands

### Environment Setup
```bash
# Install dependencies with poetry (includes dev dependencies)
make poetry

# Install dependencies without dev tools (used in CI/container)
make poetry-no-dev

# Force reinstall dependencies
make poetry force=true
```

### Running Tests

**Single cluster tests:**
```bash
# Run all Kuadrant tests (excludes multicluster and disruptive tests)
make kuadrant

# Run only Authorino-related tests
make authorino

# Run Authorino tests in standalone mode (without Kuadrant)
make authorino-standalone

# Run only Limitador (rate limiting) tests
make limitador

# Run only Kuadrant-specific tests (not compatible with standalone)
make kuadrant-only

# Run DNS and TLS policy tests
make dnstls

# Run smoke tests (quick validation)
make smoke
```

**Multicluster tests:**
```bash
make multicluster
```

**Disruptive tests:**
```bash
# Tests that may disrupt cluster state (run separately)
make disruptive
```

**Run specific test file or directory:**
```bash
# Run a specific test file
make testsuite/tests/singlecluster/authorino/test_example.py

# Run all tests in a directory
make testsuite/tests/singlecluster/limitador/

# Run with custom pytest flags
make testsuite/tests/singlecluster/authorino/ flags="-k test_name -vv"
```

**Run single test:**
```bash
poetry run python -m pytest testsuite/tests/singlecluster/path/to/test.py::test_function_name -v
```

**Parallel execution:**
```bash
# Most test targets run with 4 parallel workers by default (-n4)
make kuadrant        # Runs with -n4
make authorino       # Runs with -n4
make limitador       # Runs with -n4

# Multicluster tests use 2 workers
make multicluster    # Runs with -n2

# Disruptive tests run sequentially (no parallelization)
make disruptive      # No -n flag

# Override parallelization with custom flags
make kuadrant flags="-n8"           # Use 8 workers
make authorino flags="-n0"          # Run sequentially
make limitador flags="-n2 -vv"      # 2 workers with verbose output

# Run pytest directly with custom parallelization
poetry run pytest -n4 testsuite/tests/singlecluster/authorino/
```

### Code Quality
```bash
# Run all commit acceptance checks (black, pylint, mypy)
make commit-acceptance

# Format code with black
make reformat

# Run individual linters
make black       # Check formatting
make pylint      # Run pylint
make mypy        # Run type checking
```

### Cleanup
```bash
# Clean up all test resources from cluster
# WARNING: This deletes resources matching your username
make clean

# Clean up after another user (use with caution)
make clean USER=username
```

### Reporting
```bash
# Generate JUnit XML reports
make test junit=yes

# Generate HTML reports
make test html=yes

# Process JUnit reports for ReportPortal
make reportportal
```

## Configuration

The test suite uses **Dynaconf** for configuration management. Configuration can be provided via:

1. **Settings files** in the `config/` directory:
   - Create `config/settings.local.yaml` for local development
   - Template available at `config/settings.local.yaml.tpl`

2. **Environment variables** with `KUADRANT` prefix:
   ```bash
   export KUADRANT_SERVICE_PROTECTION__PROJECT=kuadrant
   export KUADRANT_KEYCLOAK__URL="https://sso.example.com"
   ```

### Required Configuration

- `service_protection.project` - Primary namespace for tests
- `service_protection.project2` - Secondary namespace for multi-namespace tests
- `service_protection.system_project` - Namespace where Kuadrant is installed (default: `kuadrant-system`)

### Optional Configuration

- DNS provider credentials (for DNSPolicy tests) - Secret named by `control_plane.provider_secret`
- Keycloak/Auth0 configuration (for OIDC tests)
- Multiple cluster configurations (for multicluster tests)
- Custom Gateway configuration
- Tracing backend (Jaeger/Tempo)

## Architecture

### Core Framework Components

**testsuite/kubernetes/** - Kubernetes resource abstractions
- `client.py` - KubernetesClient wrapper around openshift-client
- Custom resource classes (Deployment, Service, Secret, etc.)
- Handles resource lifecycle (create, commit, delete, wait_for_ready)

**testsuite/gateway/** - Gateway API abstractions
- `gateway_api/gateway.py` - KuadrantGateway (Gateway API)
- `gateway_api/route.py` - HTTPRoute
- `envoy/` - Envoy-specific gateway/route implementations
- `exposers.py` - Platform-specific ingress exposure (OpenShift Route, Kind, etc.)

**testsuite/kuadrant/** - Kuadrant custom resources
- `policy/authorization/` - AuthPolicy and AuthConfig
- `policy/rate_limit.py` - RateLimitPolicy
- `policy/dns.py` - DNSPolicy
- `policy/tls.py` - TLSPolicy
- `authorino.py` - Authorino CR management
- `limitador.py` - Limitador CR management

**testsuite/backend/** - Test backend services
- `httpbin.py` - Httpbin deployment
- `mockserver.py` - Mockserver deployment
- `llm_sim.py` - LLM simulator for token rate limiting tests

**testsuite/httpx/** - HTTP client utilities
- KuadrantClient - Enhanced httpx client with retry logic
- Authentication helpers (OIDC, API keys)

**testsuite/oidc/** - OIDC provider integrations
- `keycloak.py` - Keycloak management
- `auth0.py` - Auth0 provider

### Fixture Hierarchy

The test suite uses pytest fixtures organized in `conftest.py` files at multiple levels:

**Session-scoped fixtures** (created once per test run):
- `cluster` - KubernetesClient for primary cluster
- `backend` - Httpbin deployment
- `gateway` - Gateway instance (KuadrantGateway or Envoy)
- `kuadrant` - Kuadrant CR instance
- `authorino` - Authorino instance
- `oidc_provider` - Keycloak or Auth0 provider
- `label` - Unique label for test run (based on username)

**Module-scoped fixtures** (created once per test module):
- `route` - HTTPRoute or EnvoyVirtualRoute
- `authorization` - AuthPolicy or AuthConfig
- `rate_limit` - RateLimitPolicy
- `commit` - Auto-fixture that commits and waits for policies to be ready
- `client` - KuadrantClient configured for the route

**Test-scoped fixtures**:
- `auth` - HTTPX authentication object

### Fixture Customization Pattern

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
```

### Policy Lifecycle

All Kuadrant policies follow this pattern:

1. **Create instance** - `Policy.create_instance(cluster, name, target_ref)`
2. **Configure** - Call methods to add rules, conditions, etc.
3. **Commit** - `policy.commit()` applies to Kubernetes
4. **Wait for ready** - `policy.wait_for_ready()` waits for observedGeneration and Enforced condition
5. **Delete** - `policy.delete()` (usually via finalizer)

### Test Organization

**tests/singlecluster/** - Single cluster tests
- `authorino/` - Authorino/AuthPolicy tests (identity, authorization, metadata, caching)
- `limitador/` - Limitador/RateLimitPolicy tests (rate limiting, storage, metrics)
- `gateway/` - Gateway lifecycle tests (DNSPolicy, TLSPolicy, mTLS, scaling)
- `defaults/` - Default policy tests
- `overrides/` - Override policy tests
- `reconciliation/` - Policy reconciliation tests

**tests/multicluster/** - Multicluster tests
- `load_balanced/` - Load balancing across clusters
- `coredns/` - DNS delegation tests

**tests/kuadrantctl/** - Kuadrantctl CLI tests

### Pytest Markers

Use these markers to categorize tests:

- `@pytest.mark.authorino` - Uses Authorino features
- `@pytest.mark.limitador` - Uses Limitador features
- `@pytest.mark.kuadrant_only` - Requires full Kuadrant (not standalone)
- `@pytest.mark.standalone_only` - Authorino standalone mode only
- `@pytest.mark.dnspolicy` - Tests DNSPolicy
- `@pytest.mark.tlspolicy` - Tests TLSPolicy
- `@pytest.mark.multicluster` - Requires multicluster setup
- `@pytest.mark.disruptive` - May disrupt cluster state
- `@pytest.mark.smoke` - Build verification test
- `@pytest.mark.issue("URL")` - Links to GitHub issue

### Testing Patterns

**Testing rate limits:**
```python
def test_rate_limit(client):
    # Make requests up to limit
    responses = client.get_many("/get", 5)
    responses.assert_all(status_code=200)

    # Verify limit is enforced
    assert client.get("/get").status_code == 429
```

**Testing authorization:**
```python
def test_authorized(client, auth):
    # Authenticated request succeeds
    assert client.get("/get", auth=auth).status_code == 200

    # Unauthenticated request is denied
    assert client.get("/get").status_code == 401
```

**Testing policy conditions with CEL:**
```python
import pytest
from testsuite.kuadrant.policy import CelPredicate
from testsuite.kuadrant.policy.rate_limit import Limit

@pytest.fixture(scope="module")
def rate_limit(rate_limit):
    """Add conditional limits using CEL predicates"""
    rate_limit.add_limit(
        "conditional",
        [Limit(10, "1m")],
        when=[CelPredicate("request.headers['x-test'] == 'true'")]
    )
    return rate_limit
```

## Key Implementation Details

### Resource Naming
- All resources use `blame()` function to generate unique names with username prefix
- Format: `{username}-{resource-type}-{random-suffix}`
- All resources labeled with `testRun={label}` for cleanup

### Gateway Modes
The test suite supports two gateway modes:
1. **KuadrantGateway** - Gateway API (default for Kuadrant)
2. **Envoy** - Standalone Envoy (for Authorino standalone mode)

Selection is automatic based on `--standalone` flag and available gateway configuration.

### Standalone vs Kuadrant Mode
- **Standalone mode** (`--standalone` flag): Tests Authorino independently
  - Uses AuthConfig CRD directly
  - Uses Envoy gateway
  - No Kuadrant operator required
- **Kuadrant mode** (default): Tests full Kuadrant stack
  - Uses AuthPolicy CRD
  - Uses Gateway API
  - Requires Kuadrant operator

### Skip vs Fail Behavior
- By default, tests are **skipped** if required capabilities are missing
- Use `--enforce` flag to **fail** instead of skip (useful in CI)

## Development Notes

- Python 3.11+ required
- Uses `poetry` for dependency management
- Code style enforced with `black` (120 char line length)
- Type checking with `mypy`
- Linting with `pylint`
- Tests run in parallel with `pytest-xdist` (`-n4` by default)
- Uses openshift-client library for Kubernetes interactions
- httpx (with HTTP/2 support) for HTTP client operations

## Container Usage

The test suite can run in a container (see Dockerfile):

```bash
podman run \
  -v $HOME/.kube/config:/run/kubeconfig:z \
  -e KUADRANT_SERVICE_PROTECTION__PROJECT=kuadrant \
  -e KUADRANT_SERVICE_PROTECTION__PROJECT2=kuadrant2 \
  quay.io/kuadrant/testsuite:latest
```

Results are saved to `/test-run-results` in the container.