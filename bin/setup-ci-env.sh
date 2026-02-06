#!/usr/bin/env bash

# CI Environment Replication Script
# Replicates the exact CI environment from .github/workflows/test-pr.yml locally

set -e  # Exit on errors
set -o pipefail  # Exit on pipe failures

# ============================================================================
# Configuration - Versions from CI
# ============================================================================

KIND_VERSION="v0.27.0"
METALLB_VERSION="v0.15.2"
GATEWAY_API_VERSION="v1.3.0"
CERT_MANAGER_VERSION="v1.18.2"
SAIL_OPERATOR_VERSION="1.27.0"
ISTIO_VERSION="v1.24.3"

# MetalLB IP range (matches CI)
METALLB_IP_RANGE="172.18.255.200-172.18.255.250"

# KIND cluster name
KIND_CLUSTER_NAME="kuadrant-test"

# Namespaces
NAMESPACES=("kuadrant" "kuadrant2" "tools")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log file
LOG_FILE="/tmp/setup-ci-env-$(date +%Y%m%d-%H%M%S).log"

# ============================================================================
# Helper Functions
# ============================================================================

log() {
    echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $*" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[$(date +%H:%M:%S)] ✓${NC} $*" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[$(date +%H:%M:%S)] ⚠${NC} $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date +%H:%M:%S)] ✗${NC} $*" | tee -a "$LOG_FILE"
}

# ============================================================================
# Usage Information
# ============================================================================

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Create a local Kubernetes environment that replicates the CI setup.

OPTIONS:
    --skip-tools          Skip installing testsuite tools (faster setup)
    --cleanup             Delete existing cluster and start fresh
    --status              Check current environment status
    --skip-secrets        Skip creating secrets (use for testing without credentials)
    --help                Display this help message

EXAMPLES:
    $0                    # Full setup with all components
    $0 --skip-tools       # Setup without testsuite tools
    $0 --cleanup          # Remove existing cluster and recreate
    $0 --status           # Check environment status

EOF
    exit 0
}

# ============================================================================
# Status Check Function
# ============================================================================

check_status() {
    log "Checking environment status..."

    if ! kind get clusters | grep -q "^${KIND_CLUSTER_NAME}$"; then
        log_error "KIND cluster '${KIND_CLUSTER_NAME}' does not exist"
        exit 1
    fi

    echo ""
    log "Cluster nodes:"
    kubectl get nodes

    echo ""
    log "All pods:"
    kubectl get pods -A

    echo ""
    log "Kuadrant status:"
    kubectl get kuadrant -n kuadrant-system 2>/dev/null || log_warning "Kuadrant not installed"

    echo ""
    log "Gateway API CRDs:"
    kubectl get crd | grep gateway.networking.k8s.io || log_warning "Gateway API CRDs not found"

    echo ""
    log "Istio status:"
    kubectl get istio -A 2>/dev/null || log_warning "Istio not installed"

    exit 0
}

# ============================================================================
# Cleanup Function
# ============================================================================

cleanup() {
    log "Cleaning up KIND cluster '${KIND_CLUSTER_NAME}'..."
    if kind get clusters | grep -q "^${KIND_CLUSTER_NAME}$"; then
        kind delete cluster --name "$KIND_CLUSTER_NAME"
        log_success "Cluster deleted"
    else
        log_warning "Cluster '${KIND_CLUSTER_NAME}' does not exist"
    fi
    exit 0
}

# ============================================================================
# Prerequisites Check
# ============================================================================

check_prerequisites() {
    log "Checking prerequisites..."

    local missing_tools=()

    # Check required tools
    for tool in kind kubectl helm docker poetry; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done

    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_error "Please install the missing tools and try again"
        log_error ""
        log_error "Installation hints:"
        log_error "  - kind: https://kind.sigs.k8s.io/docs/user/quick-start/#installation"
        log_error "  - kubectl: https://kubernetes.io/docs/tasks/tools/"
        log_error "  - helm: https://helm.sh/docs/intro/install/"
        log_error "  - docker: https://docs.docker.com/get-docker/"
        log_error "  - poetry: pip install poetry"
        exit 1
    fi

    # Check if Docker is running
    if ! docker info &> /dev/null; then
        log_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi

    log_success "All prerequisites satisfied"
}

# ============================================================================
# cfssl installation removed - using openssl instead
# ============================================================================

# ============================================================================
# Create KIND Cluster
# ============================================================================

create_kind_cluster() {
    log "Checking KIND cluster..."

    if kind get clusters | grep -q "^${KIND_CLUSTER_NAME}$"; then
        log_success "KIND cluster '${KIND_CLUSTER_NAME}' already exists"
        return 0
    fi

    log "Creating KIND cluster '${KIND_CLUSTER_NAME}'..."
    kind create cluster --name "$KIND_CLUSTER_NAME" --wait 5m

    log_success "KIND cluster created"
}

# ============================================================================
# Install metrics-server
# ============================================================================

install_metrics_server() {
    log "Installing metrics-server..."

    kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

    # Patch for insecure TLS (required for KIND)
    kubectl patch deployment metrics-server -n kube-system --type=json \
        -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

    log_success "metrics-server installed"
}

# ============================================================================
# Install MetalLB
# ============================================================================

install_metallb() {
    log "Installing MetalLB ${METALLB_VERSION}..."

    # Apply MetalLB manifests
    kubectl apply -f "https://raw.githubusercontent.com/metallb/metallb/${METALLB_VERSION}/config/manifests/metallb-native.yaml"

    # Wait for MetalLB pods to be ready
    log "Waiting for MetalLB pods to be ready..."
    kubectl wait --namespace metallb-system \
        --for=condition=ready pod \
        --selector=app=metallb \
        --timeout=90s

    # Create IPAddressPool
    log "Creating MetalLB IPAddressPool..."
    kubectl apply -f - <<EOF
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default
  namespace: metallb-system
spec:
  addresses:
  - ${METALLB_IP_RANGE}
EOF

    # Create L2Advertisement
    log "Creating MetalLB L2Advertisement..."
    kubectl apply -f - <<EOF
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default
  namespace: metallb-system
spec:
  ipAddressPools:
  - default
EOF

    log_success "MetalLB installed and configured"
}

# ============================================================================
# Install Gateway API CRDs
# ============================================================================

install_gateway_api() {
    log "Installing Gateway API CRDs ${GATEWAY_API_VERSION}..."

    kubectl apply -f "https://github.com/kubernetes-sigs/gateway-api/releases/download/${GATEWAY_API_VERSION}/standard-install.yaml"

    log_success "Gateway API CRDs installed"
}

# ============================================================================
# Install cert-manager
# ============================================================================

install_cert_manager() {
    log "Installing cert-manager ${CERT_MANAGER_VERSION}..."

    kubectl apply -f "https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml"

    log "Waiting for cert-manager to be ready..."
    kubectl wait --namespace cert-manager \
        --for=condition=Available deployment/cert-manager \
        --timeout=120s

    log_success "cert-manager installed"
}

# ============================================================================
# Install Sail Operator
# ============================================================================

install_sail_operator() {
    log "Installing Sail Operator ${SAIL_OPERATOR_VERSION}..."

    # Add helm repo
    helm repo add sail-operator https://istio-ecosystem.github.io/sail-operator --force-update
    helm repo update

    # Install via helm
    helm install sail-operator \
        --create-namespace \
        --namespace istio-system \
        --wait \
        --timeout=300s \
        sail-operator/sail-operator \
        --version "${SAIL_OPERATOR_VERSION}"

    log_success "Sail Operator installed"
}

# ============================================================================
# Create Istio Instance
# ============================================================================

create_istio_instance() {
    log "Creating Istio instance ${ISTIO_VERSION}..."

    kubectl apply -f - <<EOF
apiVersion: sailoperator.io/v1
kind: Istio
metadata:
  name: default
spec:
  namespace: istio-system
  updateStrategy:
    type: InPlace
  values:
    pilot:
      autoscaleMin: 2
  version: ${ISTIO_VERSION}
EOF

    log "Waiting for Istio to be ready..."
    # Wait a bit for Istio to start deploying
    sleep 10
    kubectl wait --namespace istio-system \
        --for=condition=Available deployment/istiod \
        --timeout=300s || log_warning "Istio deployment may still be starting"

    log_success "Istio instance created"
}

# ============================================================================
# Create Namespaces
# ============================================================================

create_namespaces() {
    log "Creating namespaces..."

    for ns in "${NAMESPACES[@]}"; do
        if kubectl get namespace "$ns" &> /dev/null; then
            log_success "Namespace '$ns' already exists"
        else
            kubectl create namespace "$ns"
            log_success "Namespace '$ns' created"
        fi
    done
}

# ============================================================================
# Create Secrets
# ============================================================================

create_secrets() {
    log "Creating secrets..."

    # Generate self-signed CA certificate for local testing using openssl
    log "Generating self-signed CA certificate..."

    local temp_dir
    temp_dir=$(mktemp -d)
    cd "$temp_dir"

    # Generate CA private key
    openssl genrsa -out ca-key.pem 2048

    # Generate CA certificate
    openssl req -x509 -new -nodes -key ca-key.pem \
        -sha256 -days 365 -out ca.pem \
        -subj "/C=US/ST=Test/L=Local/O=Kuadrant Test/OU=Test/CN=Kuadrant Test CA"

    # Create CA secret
    kubectl create secret generic kuadrant-qe-ca \
        --namespace cert-manager \
        --from-file=tls.crt=ca.pem \
        --from-file=tls.key=ca-key.pem \
        --dry-run=client -o yaml | kubectl apply -f -

    log_success "CA certificate created"

    # Create ClusterIssuer
    kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: kuadrant-qe-issuer
spec:
  ca:
    secretName: kuadrant-qe-ca
EOF

    log_success "ClusterIssuer created"

    # Create AWS credentials secret (dummy values for local testing)
    log_warning "Creating AWS credentials secret with dummy values"
    log_warning "DNS tests requiring real AWS credentials will be skipped"

    kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: aws-credentials
  namespace: kuadrant
  annotations:
    base_domain: local.test
stringData:
  AWS_ACCESS_KEY_ID: dummy-access-key
  AWS_REGION: eu-north-1
  AWS_SECRET_ACCESS_KEY: dummy-secret-key
type: kuadrant.io/aws
EOF

    log_success "AWS credentials secret created (with dummy values)"

    # Cleanup temp directory
    rm -rf "$temp_dir"
}

# ============================================================================
# Deploy Kuadrant Operator
# ============================================================================

deploy_kuadrant_operator() {
    log "Deploying Kuadrant Operator..."

    # Add helm repo
    helm repo add kuadrant https://kuadrant.io/helm-charts/ --force-update
    helm repo update

    # Install operator
    helm install kuadrant-operator kuadrant/kuadrant-operator \
        --create-namespace \
        --namespace kuadrant-system \
        --wait \
        --timeout=300s

    log "Waiting for Kuadrant Operator deployments..."
    kubectl -n kuadrant-system wait --timeout=300s --for=condition=Available deployments --all

    log_success "Kuadrant Operator deployed"
}

# ============================================================================
# Create Kuadrant Instance
# ============================================================================

create_kuadrant_instance() {
    log "Creating Kuadrant instance..."

    kubectl apply -f - <<EOF
apiVersion: kuadrant.io/v1beta1
kind: Kuadrant
metadata:
  name: kuadrant-sample
  namespace: kuadrant-system
spec: {}
EOF

    log "Waiting for Kuadrant to be ready..."
    kubectl wait kuadrant/kuadrant-sample \
        --for=condition=Ready=True \
        -n kuadrant-system \
        --timeout=300s

    log_success "Kuadrant instance created and ready"
}

# ============================================================================
# Deploy Testsuite Tools
# ============================================================================

deploy_testsuite_tools() {
    log "Deploying testsuite tools..."

    log_warning "Skipping Red Hat registry secret (optional for local testing)"
    log_warning "If you need images from registry.redhat.io, create the secret manually"

    # Install tools chart
    helm install \
        --repo https://kuadrant.io/helm-charts-olm \
        --set=tools.keycloak.keycloakProvider=deployment \
        --set=tools.coredns.enable=false \
        --debug \
        --wait \
        --timeout=10m0s \
        tools tools-instances \
        --namespace tools

    log_success "Testsuite tools deployed"
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    # Parse command-line arguments
    local skip_tools=false
    local skip_secrets=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --help)
                usage
                ;;
            --status)
                check_status
                ;;
            --cleanup)
                cleanup
                ;;
            --skip-tools)
                skip_tools=true
                shift
                ;;
            --skip-secrets)
                skip_secrets=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                ;;
        esac
    done

    log "Starting CI environment setup..."
    log "Log file: ${LOG_FILE}"
    echo ""

    # Run setup steps
    check_prerequisites
    create_kind_cluster
    install_metrics_server
    install_metallb
    install_gateway_api
    install_cert_manager
    install_sail_operator
    create_istio_instance
    create_namespaces

    if [ "$skip_secrets" = false ]; then
        create_secrets
    else
        log_warning "Skipping secrets creation (--skip-secrets)"
    fi

    deploy_kuadrant_operator
    create_kuadrant_instance

    if [ "$skip_tools" = false ]; then
        deploy_testsuite_tools
    else
        log_warning "Skipping testsuite tools installation (--skip-tools)"
    fi

    echo ""
    log_success "=========================================="
    log_success "Environment setup completed successfully!"
    log_success "=========================================="
    echo ""
    log "To verify the installation:"
    log "  kubectl get pods -A"
    log "  kubectl get kuadrant -n kuadrant-system"
    echo ""
    log "To run tests:"
    log "  make test"
    echo ""
    log "To check environment status:"
    log "  $0 --status"
    echo ""
    log "To cleanup the environment:"
    log "  $0 --cleanup"
    echo ""
    log "Log file saved to: ${LOG_FILE}"
}

# Run main function
main "$@"
