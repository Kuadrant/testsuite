
##@ Configuration Variables

# Kind cluster configuration
KIND_CLUSTER_NAME ?= kuadrant-local

# Gateway provider (istio or envoygateway)
GATEWAYAPI_PROVIDER ?= istio

# Version pinning
ISTIO_VERSION ?= v1.27-latest
SAIL_OPERATOR_VERSION ?= v1.27-latest
ENVOYGATEWAY_VERSION ?= v1.2.4
CERT_MANAGER_VERSION ?= v1.18.2
METALLB_VERSION ?= v0.15.2
GATEWAY_API_VERSION ?= v1.3.0

# Kuadrant configuration
KUADRANT_NAMESPACE ?= kuadrant-system
KUADRANT_OPERATOR_VERSION ?= latest
KUADRANT_OPERATOR_IMAGE ?=

# Kuadrant Operator environment variables
# Default: Service timeouts for faster test execution
# Override with your own: KUADRANT_OPERATOR_ENV_VARS="LOG_LEVEL=debug,..."
KUADRANT_OPERATOR_ENV_VARS ?= AUTH_SERVICE_TIMEOUT=1000ms,RATELIMIT_SERVICE_TIMEOUT=1000ms,RATELIMIT_CHECK_SERVICE_TIMEOUT=1000ms,RATELIMIT_REPORT_SERVICE_TIMEOUT=1000ms

# Red Hat registry credentials
RH_REGISTRY_USERNAME ?=
RH_REGISTRY_PASSWORD ?=

# AWS credentials for DNS testing (optional - secret only created if provided)
AWS_ACCESS_KEY_ID ?=
AWS_SECRET_ACCESS_KEY ?=
AWS_REGION ?=
AWS_BASE_DOMAIN ?=

# Timeout configurations (in seconds)
KUBECTL_TIMEOUT ?= 300s
CERT_MANAGER_TIMEOUT ?= 120s
KUADRANT_CR_TIMEOUT ?= 120s
METALLB_TIMEOUT ?= 90s
HELM_TIMEOUT ?= 300s
TOOLS_TIMEOUT ?= 10m0s
