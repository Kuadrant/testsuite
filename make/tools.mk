
##@ Testsuite Tools

.PHONY: deploy-testsuite-tools
deploy-testsuite-tools: ## Deploy testsuite tools (Keycloak, etc.)
	@echo "Deploying testsuite tools to namespace: $(TOOLS_NAMESPACE)"
	kubectl create namespace $(TOOLS_NAMESPACE) || true
	helm repo add kuadrant-olm https://kuadrant.io/helm-charts-olm --force-update
	helm repo update
	helm install \
		--namespace $(TOOLS_NAMESPACE) \
		--set=tools.keycloak.keycloakProvider=deployment \
		--debug \
		--wait \
		--timeout=$(TOOLS_TIMEOUT) \
		tools kuadrant-olm/tools-instances
	@echo "Testsuite tools deployed"
