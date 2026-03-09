
##@ Testsuite Tools

RH_REGISTRY_USERNAME ?=
RH_REGISTRY_PASSWORD ?=

.PHONY: deploy-testsuite-tools
deploy-testsuite-tools: ## Deploy testsuite tools (Keycloak, etc.)
	@echo "Deploying testsuite tools..."
	kubectl create namespace tools || true
	@if [ -n "$(RH_REGISTRY_USERNAME)" ] && [ -n "$(RH_REGISTRY_PASSWORD)" ]; then \
		echo "Creating Red Hat registry secret..."; \
		kubectl -n tools create secret docker-registry redhat-registry-secret \
			--docker-server=registry.redhat.io \
			--docker-username="$(RH_REGISTRY_USERNAME)" \
			--docker-password="$(RH_REGISTRY_PASSWORD)" \
			--dry-run=client -o yaml | kubectl apply -f -; \
		kubectl -n tools patch serviceaccount default \
			-p '{"imagePullSecrets": [{"name": "redhat-registry-secret"}]}'; \
	else \
		echo "Red Hat registry credentials not provided, skipping secret creation"; \
	fi
	helm repo add kuadrant-olm https://kuadrant.io/helm-charts-olm --force-update
	helm repo update
	helm install \
		--set=tools.keycloak.keycloakProvider=deployment \
		--set=tools.coredns.enable=false \
		--debug \
		--wait \
		--timeout=10m0s \
		tools kuadrant-olm/tools-instances
	@echo "✅ Testsuite tools deployed"