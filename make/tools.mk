
##@ Testsuite Tools

.PHONY: deploy-testsuite-tools
deploy-testsuite-tools: ## Deploy testsuite tools (Keycloak, etc.)
	@echo "Deploying testsuite tools..."
	kubectl create namespace tools || true
	helm repo add kuadrant-olm https://kuadrant.io/helm-charts-olm --force-update
	helm repo update
	helm install \
		--set=tools.keycloak.keycloakProvider=deployment \
		--debug \
		--wait \
		--timeout=$(TOOLS_TIMEOUT) \
		tools kuadrant-olm/tools-instances
	@echo "Testsuite tools deployed"
