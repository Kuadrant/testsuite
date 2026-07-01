"""Centralized constants for the Kuadrant test suite."""

# --- Kubernetes Resource Timeouts (seconds) ---

# Additional wait after LoadBalancer IP is assigned on slow cloud providers.
SLOW_LOADBALANCER_WAIT = 60

# Default timeout for K8s wait_until condition checks.
K8S_WAIT_UNTIL_TIMEOUT = 60

# Timeout for KubernetesObject.delete() operations.
K8S_DELETE_TIMEOUT = 30

# Timeout for Deployment readiness and rollout.
DEPLOYMENT_READY_TIMEOUT = 90

# Timeout for Service/LoadBalancer readiness.
SERVICE_READY_TIMEOUT = 300  # 5 minutes

# Timeout for Service deletion (LoadBalancer cleanup can be slow).
SERVICE_DELETE_TIMEOUT = 600  # 10 minutes

# Timeout for Gateway readiness (programmed status).
GATEWAY_READY_TIMEOUT = 600  # 10 minutes

# Timeout for Route readiness (controller reconciliation).
ROUTE_READY_TIMEOUT = 10

# --- Policy Enforcement Timeouts (seconds) ---

# Default policy enforcement timeout.
POLICY_ENFORCEMENT_TIMEOUT = 60

# DNSPolicy enforcement timeout (DNS propagation is slow).
DNS_POLICY_ENFORCEMENT_TIMEOUT = 300  # 5 minutes

# TLSPolicy enforcement timeout (includes ACME challenge time).
TLS_POLICY_ENFORCEMENT_TIMEOUT = 450  # 7.5 minutes

# --- Rate Limiting (seconds) ---

# Wait after RateLimitPolicy enforcement (enforcer sync delay).
RLP_POST_ENFORCEMENT_WAIT = 5

# --- Prometheus & Observability ---

# Prometheus is_reconciled polling (~350s total).
PROMETHEUS_POLL_INTERVAL = 10
PROMETHEUS_MAX_RETRIES = 35

# Prometheus wait_for_scrape polling (~40s total).
PROMETHEUS_SCRAPE_RETRIES = 4

# Prometheus wait_for_metric polling (~50s total).
PROMETHEUS_METRIC_RETRIES = 5

# Fast Prometheus polling (~60s total).
PROMETHEUS_FAST_INTERVAL = 5
PROMETHEUS_VERIFY_NO_TARGETS_RETRIES = 12

# Tracing get_traces retry (fibonacci backoff, 7 attempts).
TRACING_MAX_RETRIES = 7

# HTTPX request retry (fibonacci backoff, 8 attempts).
HTTP_BACKOFF_MAX_RETRIES = 8

# --- SpiceDB ---

# HTTP client timeout for SpiceDB API calls (seconds).
SPICEDB_CONNECTION_TIMEOUT = 30.0

# SpiceDB relationship readiness retry (5s * 3).
SPICEDB_RETRY_INTERVAL = 5
SPICEDB_MAX_RETRIES = 3

# --- Service Ports ---

# Standard HTTP API port (shared across multiple services).
HTTP_API_PORT = 8080

# MockServer container port.
MOCKSERVER_INTERNAL_PORT = 1080

# Envoy admin interface.
ENVOY_ADMIN_PORT = 8001

# OpenTelemetry gRPC collector (Jaeger).
OTEL_COLLECTOR_PORT = 4317

# Redis / Dragonfly / Valkey.
REDIS_PORT = 6379

# HashiCorp Vault.
VAULT_PORT = 8200

# SpiceDB gRPC.
SPICEDB_GRPC_PORT = 50051

# SpiceDB HTTP/TLS.
SPICEDB_HTTP_PORT = 8443

# --- gRPC ---

# Default timeout for individual gRPC unary calls (seconds).
GRPC_CALL_TIMEOUT = 10

# --- Envoy Workarounds (seconds) ---

# Extra wait after envoy rollout (wait_for_ready alone is insufficient).
ENVOY_STARTUP_SETTLE = 3

# Envoy readiness probe initial delay.
ENVOY_READINESS_INITIAL_DELAY = 3

# Envoy readiness probe period.
ENVOY_READINESS_PERIOD = 4

# --- Mockserver readiness (seconds) ---

MOCKSERVER_READINESS_INITIAL_DELAY = 2
MOCKSERVER_READINESS_PERIOD = 2

# --- Miscellaneous Workarounds (seconds) ---

# Workaround for https://github.com/Kuadrant/testsuite/issues/884 — remove when fixed
OIDC_POST_ENFORCEMENT_WAIT = 10
