
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
	@echo "Configuring MetalLB IP pool from Docker network..."
	./utils/docker-network-ipaddresspool.sh kind | kubectl apply -n metallb-system -f -
	@echo "MetalLB installed"

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

.PHONY: install-prometheus-crds
install-prometheus-crds: ## Install only Prometheus Operator CRDs (ServiceMonitor, PodMonitor, etc.)
	@echo "Installing Prometheus Operator CRDs $(PROMETHEUS_OPERATOR_VERSION)..."
	@curl -sL https://github.com/prometheus-operator/prometheus-operator/releases/download/$(PROMETHEUS_OPERATOR_VERSION)/stripped-down-crds.yaml | \
		kubectl apply --server-side -f -
	@echo "Prometheus CRDs installed"

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
