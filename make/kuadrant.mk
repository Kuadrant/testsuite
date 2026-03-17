
##@ Kuadrant

.PHONY: create-test-namespaces
create-test-namespaces: ## Create namespaces for testing
	@echo "Creating test namespaces..."
	kubectl create namespace kuadrant || true
	kubectl create namespace kuadrant2 || true
	@echo "Test namespaces created"

.PHONY: deploy-kuadrant-operator
deploy-kuadrant-operator: ## Deploy Kuadrant Operator (mode: helm or components)
	@# Validate KUADRANT_DEPLOY_MODE
	@if [ "$(KUADRANT_DEPLOY_MODE)" != "helm" ] && [ "$(KUADRANT_DEPLOY_MODE)" != "components" ]; then \
		echo "ERROR: Invalid KUADRANT_DEPLOY_MODE='$(KUADRANT_DEPLOY_MODE)'"; \
		echo "Valid values: helm, components"; \
		exit 1; \
	fi
ifeq ($(KUADRANT_DEPLOY_MODE),components)
	@echo "Deploying Kuadrant Operator from components ($(KUADRANT_OPERATOR_VERSION))..."
	$(MAKE) deploy-kuadrant-operator-components
else
	@echo "Installing Kuadrant Operator $(KUADRANT_OPERATOR_VERSION) from Helm..."
	helm repo add kuadrant https://kuadrant.io/helm-charts/ --force-update
	$(if $(filter latest,$(KUADRANT_OPERATOR_VERSION)), \
		helm install kuadrant-operator kuadrant/kuadrant-operator --create-namespace --namespace $(KUADRANT_NAMESPACE) --wait --timeout=$(HELM_TIMEOUT), \
		helm install kuadrant-operator kuadrant/kuadrant-operator --version $(KUADRANT_OPERATOR_VERSION) --create-namespace --namespace $(KUADRANT_NAMESPACE) --wait --timeout=$(HELM_TIMEOUT))
	$(MAKE) patch-kuadrant-operator-env
	@echo "Kuadrant Operator $(KUADRANT_OPERATOR_VERSION) installed from Helm"
endif

.PHONY: patch-kuadrant-operator-env
patch-kuadrant-operator-env: ## Patch Kuadrant Operator deployment with custom env vars
ifneq ($(KUADRANT_OPERATOR_ENV_VARS),)
	@echo "Patching Kuadrant Operator with environment variables..."
	@EXISTING_ENV=$$(kubectl get deployment kuadrant-operator-controller-manager -n $(KUADRANT_NAMESPACE) -o jsonpath='{.spec.template.spec.containers[0].env}'); \
	NEW_ENV='['; \
	IFS=',' read -ra PAIRS <<< "$(KUADRANT_OPERATOR_ENV_VARS)"; \
	for i in "$${!PAIRS[@]}"; do \
		PAIR="$${PAIRS[$$i]}"; \
		NAME=$$(echo "$$PAIR" | cut -d'=' -f1); \
		VALUE=$$(echo "$$PAIR" | cut -d'=' -f2-); \
		[ $$i -gt 0 ] && NEW_ENV="$$NEW_ENV,"; \
		NEW_ENV="$$NEW_ENV{\"name\":\"$$NAME\",\"value\":\"$$VALUE\"}"; \
	done; \
	NEW_ENV="$$NEW_ENV]"; \
	MERGED_ENV=$$(echo "$$EXISTING_ENV$$NEW_ENV" | jq -s '.[0] + .[1] | unique_by(.name)'); \
	kubectl patch deployment kuadrant-operator-controller-manager -n $(KUADRANT_NAMESPACE) \
		--type=json -p="[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/env\",\"value\":$$MERGED_ENV}]"; \
	kubectl -n $(KUADRANT_NAMESPACE) rollout status deployment/kuadrant-operator-controller-manager --timeout=$(KUBECTL_TIMEOUT)
	@echo "Kuadrant Operator patched with env vars"
else
	@echo "No custom env vars specified (KUADRANT_OPERATOR_ENV_VARS not set)"
endif

.PHONY: deploy-kuadrant-cr
deploy-kuadrant-cr: ## Deploy Kuadrant CR
	@echo "Creating Kuadrant CR..."
	@printf '%s\n' \
		'apiVersion: kuadrant.io/v1beta1' \
		'kind: Kuadrant' \
		'metadata:' \
		'  name: kuadrant-sample' \
		'  namespace: $(KUADRANT_NAMESPACE)' \
		'spec: {}' \
		| kubectl apply -f -
	kubectl wait kuadrant/kuadrant-sample --for=condition=Ready=True -n $(KUADRANT_NAMESPACE) --timeout=$(KUADRANT_CR_TIMEOUT)
	@echo "Kuadrant CR ready"
