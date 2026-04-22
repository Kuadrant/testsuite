
##@ Configuration Variables

# Kind cluster configuration
KIND_CLUSTER_NAME ?= kuadrant-local

# Gateway provider (istio or envoygateway)
GATEWAYAPI_PROVIDER ?= istio

# Version pinning
ISTIO_VERSION ?= v1.26-latest
SAIL_OPERATOR_VERSION ?= v1.26-latest
ENVOYGATEWAY_VERSION ?= v1.2.4
CERT_MANAGER_VERSION ?= v1.18.2
METALLB_VERSION ?= v0.15.2
GATEWAY_API_VERSION ?= v1.3.0
PROMETHEUS_OPERATOR_VERSION ?= v0.78.2

# Kuadrant configuration
KUADRANT_NAMESPACE ?= kuadrant-system
KUADRANT_OPERATOR_VERSION ?= latest
KUADRANT_OPERATOR_IMAGE ?=

# Kuadrant deployment mode: "components" (GitHub kustomize, default) or "helm" (stable releases)
KUADRANT_DEPLOY_MODE ?= components

# Component versions (used when KUADRANT_DEPLOY_MODE=components)
KUADRANT_OPERATOR_GITREF = $(if $(filter latest,$(KUADRANT_OPERATOR_VERSION)),main,$(KUADRANT_OPERATOR_VERSION))

# Kuadrant Operator environment variables
# Default: Service timeouts for faster test execution
# Override with your own: KUADRANT_OPERATOR_ENV_VARS="LOG_LEVEL=debug,..."
KUADRANT_OPERATOR_ENV_VARS ?= AUTH_SERVICE_TIMEOUT=1000ms,RATELIMIT_SERVICE_TIMEOUT=1000ms,RATELIMIT_CHECK_SERVICE_TIMEOUT=1000ms,RATELIMIT_REPORT_SERVICE_TIMEOUT=1000ms,TRACING_SERVICE_TIMEOUT=1000ms,DNS_DEFAULT_TTL=1,DNS_DEFAULT_LB_TTL=1

# Additional manifests to apply during setup (optional - e.g., secrets, configmaps)
# Point to a YAML file containing any additional Kubernetes resources
ADDITIONAL_MANIFESTS ?=

# Tools namespace (Jaeger, Keycloak, etc.)
TOOLS_NAMESPACE ?= tools

# Tracing configuration
INSTALL_TRACING ?= true
JAEGER_COLLECTOR_ENDPOINT ?= http://jaeger-collector.$(TOOLS_NAMESPACE).svc.cluster.local:4318

# Timeout configurations (in seconds)
KUBECTL_TIMEOUT ?= 300s
CERT_MANAGER_TIMEOUT ?= 120s
KUADRANT_CR_TIMEOUT ?= 120s
METALLB_TIMEOUT ?= 90s
HELM_TIMEOUT ?= 300s
TOOLS_TIMEOUT ?= 10m0s
