
##@ Local Environment Setup

GATEWAYAPI_PROVIDER ?= istio

.PHONY: local-setup
local-setup: ## Complete local environment setup (kind cluster + all dependencies)
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