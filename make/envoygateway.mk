
##@ EnvoyGateway

.PHONY: envoygateway-install
envoygateway-install: ## Install EnvoyGateway
	@echo "Installing EnvoyGateway..."
	helm install eg oci://docker.io/envoyproxy/gateway-helm --version v1.2.4 \
		--create-namespace \
		--namespace envoy-gateway-system \
		--wait
	@echo "✅ EnvoyGateway installed"