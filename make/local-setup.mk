
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
	@echo ""
	@echo "Run tests with: make kuadrant"

.PHONY: local-cleanup
local-cleanup: ## Delete local kind cluster
	$(MAKE) kind-delete-cluster
