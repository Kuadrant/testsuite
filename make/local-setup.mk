
##@ Local Environment Setup

.PHONY: local-setup
local-setup: ## Complete local environment setup (kind cluster + all dependencies)
	@# Validate GATEWAYAPI_PROVIDER
	@if [ "$(GATEWAYAPI_PROVIDER)" != "istio" ] && [ "$(GATEWAYAPI_PROVIDER)" != "envoygateway" ]; then \
		echo "ERROR: Invalid GATEWAYAPI_PROVIDER='$(GATEWAYAPI_PROVIDER)'"; \
		echo "Valid values: istio, envoygateway"; \
		exit 1; \
	fi
	@echo "Using Kuadrant deployment mode: $(KUADRANT_DEPLOY_MODE)"
	@echo "  (Change with: KUADRANT_DEPLOY_MODE=components make local-setup)"
	$(MAKE) kind-delete-cluster
	$(MAKE) kind-create-cluster
	$(MAKE) install-metrics-server
	$(MAKE) install-metallb
	$(MAKE) gateway-api-install
	$(MAKE) install-cert-manager
	$(MAKE) create-cluster-issuer
	$(MAKE) install-prometheus
	$(MAKE) $(GATEWAYAPI_PROVIDER)-install
	$(MAKE) create-test-namespaces
	$(MAKE) apply-additional-manifests
	$(MAKE) deploy-kuadrant-operator
	$(MAKE) deploy-kuadrant-cr
	$(MAKE) deploy-testsuite-tools
	@echo ""
	@echo "Local environment setup complete!"
	@echo "   Cluster: $(KIND_CLUSTER_NAME)"
	@echo "   Gateway Provider: $(GATEWAYAPI_PROVIDER)"
ifeq ($(INSTALL_PROMETHEUS),true)
	@echo "   Prometheus: Enabled (namespace: $(PROMETHEUS_NAMESPACE))"
	@HOST=$$(kubectl get svc -n $(PROMETHEUS_NAMESPACE) prometheus-kube-prometheus-prometheus \
		-o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null); \
	[ -z "$$HOST" ] && HOST=$$(kubectl get svc -n $(PROMETHEUS_NAMESPACE) prometheus-kube-prometheus-prometheus \
		-o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null); \
	[ -n "$$HOST" ] && echo "   Prometheus URL: http://$$HOST:9090"
endif
	@echo ""
	@echo "Run tests with: make kuadrant"
ifeq ($(INSTALL_PROMETHEUS),true)
	@echo ""
	@echo "For observability tests: make observability"
endif

.PHONY: local-cleanup
local-cleanup: ## Delete local kind cluster
	$(MAKE) kind-delete-cluster
