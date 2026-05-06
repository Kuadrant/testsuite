
##@ Core Dependencies

.PHONY: install-metrics-server
install-metrics-server: ## Install metrics-server
	@echo "Installing metrics-server..."
	kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
	kubectl patch deployment metrics-server -n kube-system --type=json -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
	@echo "metrics-server installed"

.PHONY: install-metallb
install-metallb: ## Install MetalLB for LoadBalancer services
	@echo "Installing MetalLB $(METALLB_VERSION)..."
	kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/$(METALLB_VERSION)/config/manifests/metallb-native.yaml
	kubectl wait --namespace metallb-system --for=condition=Available deployment/controller --timeout=$(METALLB_TIMEOUT)
	kubectl wait --namespace metallb-system --for=condition=ready pod --selector=component=controller --timeout=$(METALLB_TIMEOUT)
	@echo "Configuring MetalLB IP pool..."
	@printf '%s\n' \
		'apiVersion: metallb.io/v1beta1' \
		'kind: IPAddressPool' \
		'metadata:' \
		'  name: default' \
		'  namespace: metallb-system' \
		'spec:' \
		'  addresses:' \
		'  - 172.18.255.200-172.18.255.250' \
		| kubectl apply -f -
	@printf '%s\n' \
		'apiVersion: metallb.io/v1beta1' \
		'kind: L2Advertisement' \
		'metadata:' \
		'  name: default' \
		'  namespace: metallb-system' \
		| kubectl apply -f -
	@echo "MetalLB installed with IP pool 172.18.255.200-172.18.255.250"

.PHONY: gateway-api-install
gateway-api-install: ## Install Gateway API CRDs
	@echo "Installing Gateway API $(GATEWAY_API_VERSION)..."
	kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/$(GATEWAY_API_VERSION)/standard-install.yaml
	@echo "Gateway API CRDs installed"

.PHONY: install-cert-manager
install-cert-manager: ## Install cert-manager
	@echo "Installing cert-manager $(CERT_MANAGER_VERSION)..."
	kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/$(CERT_MANAGER_VERSION)/cert-manager.yaml
	kubectl wait --namespace cert-manager --for=condition=Available deployment/cert-manager --timeout=$(CERT_MANAGER_TIMEOUT)
	kubectl wait --namespace cert-manager --for=condition=Available deployment/cert-manager-webhook --timeout=$(CERT_MANAGER_TIMEOUT)
	kubectl wait --namespace cert-manager --for=condition=ready pod --selector=app.kubernetes.io/name=webhook --timeout=$(CERT_MANAGER_TIMEOUT)
	@echo "cert-manager installed"

.PHONY: create-cluster-issuer
create-cluster-issuer: ## Create self-signed ClusterIssuer for TLS testing
	@echo "Creating self-signed ClusterIssuer..."
	@printf '%s\n' \
		'apiVersion: cert-manager.io/v1' \
		'kind: ClusterIssuer' \
		'metadata:' \
		'  name: kuadrant-qe-issuer' \
		'spec:' \
		'  selfSigned: {}' \
		| kubectl apply -f -
	@echo "ClusterIssuer 'kuadrant-qe-issuer' created"

.PHONY: install-prometheus
install-prometheus: ## Install Prometheus stack (full or CRDs only based on INSTALL_PROMETHEUS)
ifeq ($(INSTALL_PROMETHEUS),true)
	@echo "Installing Prometheus stack $(PROMETHEUS_STACK_VERSION)..."
	kubectl create namespace $(PROMETHEUS_NAMESPACE) || true
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update
	helm install prometheus prometheus-community/kube-prometheus-stack \
		--version $(PROMETHEUS_STACK_VERSION) \
		--namespace $(PROMETHEUS_NAMESPACE) \
		--create-namespace \
		--wait \
		--timeout=$(HELM_TIMEOUT) \
		--set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
		--set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false \
		--set prometheus.prometheusSpec.ruleSelectorNilUsesHelmValues=false \
		--set prometheus.service.type=LoadBalancer
	@echo "Prometheus stack installed in $(PROMETHEUS_NAMESPACE) namespace"
	@echo ""
	@echo "Waiting for LoadBalancer IP assignment..."
	@kubectl wait --for=jsonpath='{.status.loadBalancer.ingress[0].ip}' \
		svc/prometheus-kube-prometheus-prometheus -n $(PROMETHEUS_NAMESPACE) --timeout=60s 2>/dev/null || true
	@PROM_URL=$$(kubectl get svc -n $(PROMETHEUS_NAMESPACE) prometheus-kube-prometheus-prometheus \
		-o jsonpath='http://{.status.loadBalancer.ingress[0].ip}:9090' 2>/dev/null); \
	if [ -n "$$PROM_URL" ]; then \
		echo "Prometheus accessible at: $$PROM_URL"; \
	else \
		echo "WARNING: LoadBalancer IP not yet assigned. Run 'make get-prometheus-url' once ready."; \
	fi
else
	@echo "Installing Prometheus Operator CRDs $(PROMETHEUS_OPERATOR_VERSION)..."
	@curl -sL https://github.com/prometheus-operator/prometheus-operator/releases/download/$(PROMETHEUS_OPERATOR_VERSION)/stripped-down-crds.yaml | \
		kubectl apply --server-side -f -
	@echo "Prometheus CRDs installed (to install full stack, use INSTALL_PROMETHEUS=true)"
endif

.PHONY: apply-additional-manifests
apply-additional-manifests: ## Apply additional manifests from file (if ADDITIONAL_MANIFESTS is set)
	@if [ -n "$(ADDITIONAL_MANIFESTS)" ]; then \
		if [ -f "$(ADDITIONAL_MANIFESTS)" ]; then \
			echo "Applying additional manifests from $(ADDITIONAL_MANIFESTS)..."; \
			kubectl apply -f "$(ADDITIONAL_MANIFESTS)"; \
			echo "Additional manifests applied"; \
		else \
			echo "❌ Error: ADDITIONAL_MANIFESTS file '$(ADDITIONAL_MANIFESTS)' not found"; \
			exit 1; \
		fi; \
	else \
		echo "⏭️  No additional manifests to apply (ADDITIONAL_MANIFESTS not set)"; \
	fi
