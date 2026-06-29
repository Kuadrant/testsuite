
##@ Core Dependencies

.PHONY: install-metrics-server
install-metrics-server: ## Install metrics-server
	@echo "Installing metrics-server..."
	kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
	kubectl patch deployment metrics-server -n kube-system --type=json -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
	@echo "metrics-server installed"

.PHONY: start-cloud-provider
start-cloud-provider: ## Start cloud-provider-kind for LoadBalancer services
	@if ! command -v cloud-provider-kind >/dev/null 2>&1; then \
		echo "ERROR: cloud-provider-kind not found."; \
		echo "Install it with: go install sigs.k8s.io/cloud-provider-kind@latest"; \
		echo "  or on macOS: brew install cloud-provider-kind"; \
		exit 1; \
	fi
	@if [ "$$(uname)" = "Darwin" ]; then \
		sudo pkill -f cloud-provider-kind 2>/dev/null || true; \
	elif [ -f /tmp/cloud-provider-kind.pid ]; then \
		PID=$$(cat /tmp/cloud-provider-kind.pid); \
		kill -9 $$PID 2>/dev/null || true; \
		rm -f /tmp/cloud-provider-kind.pid; \
		echo "Stopped existing cloud-provider-kind (PID $$PID)"; \
	fi
	@DOCKER_HOST_ENV=""; \
	if $(CONTAINER_ENGINE) --version 2>/dev/null | grep -qi podman; then \
		if [ "$$(uname)" = "Darwin" ]; then \
			SOCKET="$$(podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}' 2>/dev/null)"; \
		else \
			SOCKET="$$(podman info --format '{{.Host.RemoteSocket.Path}}' 2>/dev/null)"; \
		fi; \
		if [ -n "$$SOCKET" ] && [ -S "$$SOCKET" ]; then \
			DOCKER_HOST_ENV="DOCKER_HOST=unix://$$SOCKET"; \
			echo "Detected podman, using socket: $$SOCKET"; \
		else \
			echo "ERROR: Podman detected, but no Docker-compatible socket was found."; \
			if [ "$$(uname)" = "Darwin" ]; then \
				echo "ERROR: Check 'podman machine start' or 'podman machine inspect'."; \
			else \
				echo "ERROR: Use 'systemctl --user status podman.socket' to check status."; \
				echo "  On Linux, enable the podman socket: systemctl --user start podman.socket"; \
			fi; \
			exit 1; \
		fi; \
	fi; \
	echo "Starting cloud-provider-kind..."; \
	if [ "$$(uname)" = "Darwin" ]; then \
		sudo env $$DOCKER_HOST_ENV cloud-provider-kind > /tmp/cloud-provider-kind.log 2>&1 & \
	else \
		env $$DOCKER_HOST_ENV cloud-provider-kind --enable-lb-port-mapping > /tmp/cloud-provider-kind.log 2>&1 & \
		echo $$! > /tmp/cloud-provider-kind.pid; \
	fi; \
	sleep 2; \
	echo "cloud-provider-kind started (log: /tmp/cloud-provider-kind.log)"

.PHONY: stop-cloud-provider
stop-cloud-provider: ## Stop cloud-provider-kind background process
	@echo "Stopping cloud-provider-kind..."
	@if [ "$$(uname)" = "Darwin" ]; then \
		sudo pkill -f cloud-provider-kind 2>/dev/null || true; \
	elif [ -f /tmp/cloud-provider-kind.pid ]; then \
		PID=$$(cat /tmp/cloud-provider-kind.pid); \
		kill -9 $$PID 2>/dev/null || true; \
		rm -f /tmp/cloud-provider-kind.pid; \
	fi
	@echo "cloud-provider-kind stopped"

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
