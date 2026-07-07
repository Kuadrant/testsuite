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

# Policy condition check timeout.
POLICY_CONDITION_TIMEOUT = 20

# Object deletion check timeout.
OBJECT_DELETION_TIMEOUT = 30

# DNS health check timeout.
DNS_HEALTH_CHECK_TIMEOUT = 120  # 2 minutes

# --- Rate Limiting (seconds) ---

# Wait after RateLimitPolicy enforcement (enforcer sync delay).
RLP_POST_ENFORCEMENT_WAIT = 5

# Wait for RLP window reset.
RLP_WINDOW_RESET_WAIT = 5

# Wait for RLP window reset with safety buffer.
RLP_WINDOW_RESET_WAIT_BUFFERED = 6

# Wait for RLP counter reset.
RLP_COUNTER_RESET_WAIT = 15

# Wait for RLP iteration window to reset.
RLP_ITERATION_WINDOW_RESET_WAIT = 10

# --- Token Rate Limiting (seconds) ---

# Wait for TRLP free user quota reset.
TRLP_FREE_USER_RESET_WAIT = 30

# Wait for TRLP paid user quota reset.
TRLP_PAID_USER_RESET_WAIT = 60

# Wait for TRLP iteration reset.
TRLP_ITERATION_RESET_WAIT = 20

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

# Observability ServiceMonitor/PodMonitor readiness polling (~60s total).
OBSERVABILITY_MONITOR_POLL_INTERVAL = 5
OBSERVABILITY_MONITOR_MAX_RETRIES = 12

# --- SpiceDB ---

# HTTP client timeout for SpiceDB API calls (seconds).
SPICEDB_CONNECTION_TIMEOUT = 30.0

# SpiceDB relationship readiness retry (5s * 3).
SPICEDB_RETRY_INTERVAL = 5
SPICEDB_MAX_RETRIES = 3

# --- Service Ports ---

# Standard HTTP port.
HTTP_PORT = 80

# Standard HTTPS port.
HTTPS_PORT = 443

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

# Authorino OIDC wristband endpoint.
AUTHORINO_OIDC_PORT = 8083

# --- gRPC ---

# Default timeout for individual gRPC unary calls (seconds).
GRPC_CALL_TIMEOUT = 10

# --- Envoy Workarounds (seconds) ---

# Wait after Envoy rollout (wait_for_ready alone is insufficient).
ENVOY_STARTUP_SETTLE = 3

# Envoy readiness probe initial delay.
ENVOY_READINESS_INITIAL_DELAY = 3

# Envoy readiness probe period.
ENVOY_READINESS_PERIOD = 4

# --- DNS Propagation (seconds) ---

# DNS propagation wait.
DNS_PROPAGATION_WAIT = 300  # 5 minutes
# --- Mockserver readiness (seconds) ---

MOCKSERVER_READINESS_INITIAL_DELAY = 2
MOCKSERVER_READINESS_PERIOD = 2

# --- Miscellaneous Workarounds (seconds) ---

# Workaround for https://github.com/Kuadrant/testsuite/issues/884 — remove when fixed
OIDC_POST_ENFORCEMENT_WAIT = 10

# Wait for OPA external registry cache TTL to expire (TTL + buffer).
OPA_CACHE_TTL_WAIT = 2

# Wait for TLS secret deletion to propagate.
TLS_SECRET_PROPAGATION_WAIT = 10

# Kind workaround: wait for WasmPlugin sync before https://github.com/envoyproxy/envoy/pull/43928 is released.
WASM_PLUGIN_SYNC_WAIT = 15

# Max retry attempts for JWT test startup.
JWT_STARTUP_MAX_RETRIES = 20
