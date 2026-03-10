
##@ Local Environment Setup

.PHONY: local-setup
local-setup: ## Complete local environment setup (kind cluster + all dependencies)
	@# Validate GATEWAYAPI_PROVIDER
	@if [ "$(GATEWAYAPI_PROVIDER)" != "istio" ] && [ "$(GATEWAYAPI_PROVIDER)" != "envoygateway" ]; then \
		echo "ERROR: Invalid GATEWAYAPI_PROVIDER='$(GATEWAYAPI_PROVIDER)'"; \
		echo "Valid values: istio, envoygateway"; \
		exit 1; \
	fi
	$(MAKE) kind-delete-cluster
	$(MAKE) kind-create-cluster
	$(MAKE) install-metrics-server
	$(MAKE) install-metallb
	$(MAKE) gateway-api-install
	$(MAKE) install-cert-manager
	$(MAKE) $(GATEWAYAPI_PROVIDER)-install
	$(MAKE) create-test-namespaces
	$(MAKE) deploy-kuadrant-operator
	$(MAKE) deploy-kuadrant-cr
	$(MAKE) deploy-testsuite-tools
	@echo ""
	@echo "🎉 Local environment setup complete!"
	@echo "   Cluster: $(KIND_CLUSTER_NAME)"
	@echo "   Gateway Provider: $(GATEWAYAPI_PROVIDER)"
	@echo ""
	@echo "Run tests with: make kuadrant"

.PHONY: local-cleanup
local-cleanup: ## Delete local kind cluster
	$(MAKE) kind-delete-cluster