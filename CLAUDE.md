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

# Complete local setup (creates kind cluster + installs all components)
make local-setup                                                       # Default: components mode (latest from GitHub)

# Use Helm instead of components mode
KUADRANT_DEPLOY_MODE=helm make local-setup

# Enable Prometheus CRDs for observability testing (ServiceMonitor, PodMonitor)
INSTALL_PROMETHEUS=true make local-setup

# Apply additional manifests during setup (e.g., DNS credentials, secrets)
ADDITIONAL_MANIFESTS=./my-secrets.yaml make local-setup

# Deploy specific versions
AUTHORINO_OPERATOR_VERSION=v0.13.0 \
  LIMITADOR_OPERATOR_VERSION=v1.5.0 \
  DNS_OPERATOR_VERSION=v0.8.0 \
  make local-setup                                                     # Components: specific versions
KUADRANT_DEPLOY_MODE=helm KUADRANT_OPERATOR_VERSION=v0.10.0 \
  make local-setup                                                     # Helm: specific version
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

## Pull Request Guidelines

For PR title format and commit conventions, see `.claude/commands/pr-description.md` or use the `/pr-description` command.

## Configuration and Settings

### Settings File

Template with all configuration options: `config/settings.local.yaml.tpl`

The testsuite uses Dynaconf for configuration management. Settings are loaded from `config/settings.yaml` and can be overridden via `config/settings.local.yaml` or environment variables with the `KUADRANT_` prefix (e.g., `KUADRANT_RHSSO__url`).

### Cluster Connection (Required)

The only required setting is a cluster connection. It can be set via either kubeconfig or token:

```yaml
default:
  control_plane:
    cluster:
      kubeconfig_path: "~/.kube/config"         # Option 1: kubeconfig
      # OR
      api_url: "https://api.cluster.kuadrant-qe.net:6443"     # Option 2: API URL + token
      token: "abcde12345_token"
```

### External Service Connections

External services (Keycloak, Mockserver, Jaeger/Tempo, Redis, etc.) can be configured in two ways:

1. **Auto-fetched from the cluster** (default): If services are deployed in the `tools` namespace on the test cluster, the testsuite automatically discovers their connection URLs via `DefaultValueValidator` in `testsuite/config/__init__.py`. The auto-fetch helpers (`fetch_service_ip`, `fetch_secret` in `testsuite/config/tools.py`) look up LoadBalancer IPs and secrets from the cluster.

2. **Explicitly set in settings**: Override the auto-fetched values by specifying the URL directly in `config/settings.local.yaml` or via environment variables.

```yaml
default:
  # Keycloak: auto-fetched from 'keycloak' service in tools namespace,
  # password from 'credential-sso' secret. Override with explicit values:
  keycloak:
    url: "http://keycloak.example.com:8080"
    username: "admin"
    password: "admin-password"
    test_user:
      username: "testUser"  # name of the keycloak realm user for the tests
      password: "testPassword"  # password of the keycloak realm user for the tests

  # Mockserver: auto-fetched from 'mockserver' service in tools namespace.
  # Override with explicit URL:
  mockserver:
    url: "http://10.0.25.192:1080"
    image: "mockserver/mockserver:latest"       # Image for self-deployed MockserverBackend
```

If auto-fetch fails (service not found on cluster) and no explicit value is set, tests requiring that service are automatically skipped.

### Settings Validation

Settings validation is defined in `testsuite/config/__init__.py`. Validators run at startup for required settings and lazily for optional ones. Test fixtures validate their required config sections before use:

```python
@pytest.fixture(scope="session")
def keycloak(request, testconfig, blame, skip_or_fail):
    """Keycloak OIDC Provider fixture"""
    testconfig.validators.validate(only="keycloak")  # Validates keycloak config section
    cnf = testconfig["keycloak"]
    # ... setup keycloak
```

Tests automatically skip when their required configuration is missing.

## Test Suite Structure

### Test Modules

**testsuite/tests/singlecluster/**: Single-cluster test scenarios
- `authorino/`: Authorino-specific features (identity verification, metadata, authorization, response manipulation)
- `limitador/`: Rate limiting tests
- `gateway/`: Gateway API behavior tests (DNS/TLS policy)
- `observability/`: Metrics and monitoring tests
- `reconciliation/`: Resource reconciliation tests
- `defaults/`: Default policy behavior
- `overrides/`: Policy override behavior
- `identical_hostnames/`: Multi-gateway hostname conflict tests

**testsuite/tests/multicluster/**: Multi-cluster test scenarios
- `coredns/`: CoreDNS integration tests
- `load_balanced/`: Load balancing across clusters

### Pytest Markers

Tests use markers to categorize functionality. All available markers are defined in `pyproject.toml` under `[tool.pytest.ini_options]`. Common markers:

- `@pytest.mark.authorino` - Authorino-specific tests
- `@pytest.mark.limitador` - Limitador-specific tests
- `@pytest.mark.kuadrant_only` - Tests requiring full Kuadrant (not standalone)
- `@pytest.mark.standalone_only` - Standalone mode tests
- `@pytest.mark.smoke` - Smoke tests
- `@pytest.mark.issue("https://github.com/...")` - Linked to GitHub/Jira issues
- `@pytest.mark.min_ocp_version((4, 20))` - Minimum OpenShift version requirement

### Test Reruns (`@pytest.mark.flaky`)

See `.claude/rules/test-reruns.md` for detailed guidance on using `@pytest.mark.flaky` to control rerun behavior per test.

## Coding Conventions

### Docstrings

**Every module and fixture must have a short, descriptive docstring.** Module-level docstrings describe the test scope. Fixture docstrings describe what they create or return, not how.

### Fixture Naming

Fixtures should have simple, descriptive names like `route`, `authorization`, `backend`, `gateway`, `hostname`, `client`. When a test requires multiple instances of the same resource, append a number to the secondary resources: `route2`, `backend2`, `authorization2`, etc. The primary resource always uses the plain name without a number.

### Resource Naming with `blame()`

The `blame()` fixture generates unique, scoped names for Kubernetes resources:

```python
blame("gw")       # -> "gw-alice-tc-abc"
blame("route")    # -> "route-alice-modname-jkl"
```

### Fixture Scopes

- `scope="session"` - Created once per test run: `cluster`, `backend`, `gateway`, `exposer` (usually located in `testsuite/tests/conftest.py`)
- `scope="module"` - Created per test module: `route`, `authorization`, `rate_limit`, `hostname`, `client`
- `scope="function"` - Created per test: rarely used, only for parametrized or stateful tests

### Pylint Disable Guidelines

**Always look for a more correct solution before disabling a warning.** Common legitimate uses:

- `# pylint: disable=unused-argument` - Fixtures that need to be in the signature for pytest dependency ordering but aren't directly used in the function body
- `# pylint: disable=invalid-name` - Dataclass fields that must match Kubernetes API camelCase naming (e.g., `matchExpressions`, `sectionName`)
