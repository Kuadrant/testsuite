
##@ Testsuite Tools

.PHONY: deploy-testsuite-tools
deploy-testsuite-tools: ## Deploy testsuite tools (Keycloak, etc.) - requires RH_REGISTRY credentials
	@if [ -n "$(RH_REGISTRY_USERNAME)" ] && [ -n "$(RH_REGISTRY_PASSWORD)" ]; then \
		echo "Deploying testsuite tools..."; \
		kubectl create namespace tools || true; \
		echo "Creating Red Hat registry secret..."; \
		kubectl -n tools create secret docker-registry redhat-registry-secret \
			--docker-server=registry.redhat.io \
			--docker-username="$(RH_REGISTRY_USERNAME)" \
			--docker-password="$(RH_REGISTRY_PASSWORD)" \
			--dry-run=client -o yaml | kubectl apply -f -; \
		kubectl -n tools patch serviceaccount default \
			-p '{"imagePullSecrets": [{"name": "redhat-registry-secret"}]}'; \
		helm repo add kuadrant-olm https://kuadrant.io/helm-charts-olm --force-update; \
		helm repo update; \
		helm install \
			--set=tools.keycloak.keycloakProvider=deployment \
			--set=tools.coredns.enable=false \
			--debug \
			--wait \
			--timeout=$(TOOLS_TIMEOUT) \
			tools kuadrant-olm/tools-instances; \
		echo "Testsuite tools deployed"; \
	else \
		echo "⏭️  Skipping testsuite tools deployment (requires RH_REGISTRY_USERNAME and RH_REGISTRY_PASSWORD)"; \
	fi
