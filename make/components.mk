
##@ Component Deployment (Direct from GitHub)

# Component versions (when not using Helm)
AUTHORINO_OPERATOR_VERSION ?= latest
LIMITADOR_OPERATOR_VERSION ?= latest
DNS_OPERATOR_VERSION ?= latest

# Convert "latest" to "main" for GitHub refs, otherwise use as-is (e.g., v0.13.0)
AUTHORINO_GITREF = $(if $(filter latest,$(AUTHORINO_OPERATOR_VERSION)),main,$(AUTHORINO_OPERATOR_VERSION))
LIMITADOR_GITREF = $(if $(filter latest,$(LIMITADOR_OPERATOR_VERSION)),main,$(LIMITADOR_OPERATOR_VERSION))
DNS_GITREF = $(if $(filter latest,$(DNS_OPERATOR_VERSION)),main,$(DNS_OPERATOR_VERSION))

.PHONY: deploy-authorino-operator
deploy-authorino-operator: ## Deploy Authorino Operator
	@echo "Deploying Authorino Operator ($(AUTHORINO_GITREF)) to $(KUADRANT_NAMESPACE)..."
	@mkdir -p /tmp/kuadrant-kustomize-authorino
	@printf '%s\n' \
		'namespace: $(KUADRANT_NAMESPACE)' \
		'resources:' \
		'- github.com/Kuadrant/authorino-operator/config/deploy?ref=$(AUTHORINO_GITREF)' \
		> /tmp/kuadrant-kustomize-authorino/kustomization.yaml
	kubectl apply --server-side -k /tmp/kuadrant-kustomize-authorino
	@rm -rf /tmp/kuadrant-kustomize-authorino
	@echo "Authorino Operator deployed"

.PHONY: deploy-limitador-operator
deploy-limitador-operator: ## Deploy Limitador Operator
	@echo "Deploying Limitador Operator ($(LIMITADOR_GITREF)) to $(KUADRANT_NAMESPACE)..."
	@mkdir -p /tmp/kuadrant-kustomize-limitador
	@printf '%s\n' \
		'namespace: $(KUADRANT_NAMESPACE)' \
		'resources:' \
		'- github.com/Kuadrant/limitador-operator/config/default?ref=$(LIMITADOR_GITREF)' \
		> /tmp/kuadrant-kustomize-limitador/kustomization.yaml
	kubectl apply --server-side -k /tmp/kuadrant-kustomize-limitador
	@rm -rf /tmp/kuadrant-kustomize-limitador
	@echo "Limitador Operator deployed"

.PHONY: deploy-dns-operator
deploy-dns-operator: ## Deploy DNS Operator
	@echo "Deploying DNS Operator ($(DNS_GITREF)) to $(KUADRANT_NAMESPACE)..."
	@mkdir -p /tmp/kuadrant-kustomize-dns
	@printf '%s\n' \
		'namespace: $(KUADRANT_NAMESPACE)' \
		'resources:' \
		'- github.com/kuadrant/dns-operator/config/default?ref=$(DNS_GITREF)' \
		> /tmp/kuadrant-kustomize-dns/kustomization.yaml
	kubectl apply --server-side -k /tmp/kuadrant-kustomize-dns
	@rm -rf /tmp/kuadrant-kustomize-dns
	@echo "DNS Operator deployed"

.PHONY: deploy-kuadrant-operator-components
deploy-kuadrant-operator-components: ## Deploy Kuadrant Operator from components
	kubectl create namespace $(KUADRANT_NAMESPACE) || true
	$(MAKE) deploy-authorino-operator
	$(MAKE) deploy-limitador-operator
	$(MAKE) deploy-dns-operator
	@echo "Deploying Kuadrant Operator ($(KUADRANT_OPERATOR_GITREF)) to $(KUADRANT_NAMESPACE)..."
	kubectl apply --server-side -k "github.com/kuadrant/kuadrant-operator/config/deploy?ref=$(KUADRANT_OPERATOR_GITREF)"
	@echo "Waiting for all operator deployments to be ready..."
	kubectl -n $(KUADRANT_NAMESPACE) wait --timeout=$(KUBECTL_TIMEOUT) --for=condition=Available deployments --all
	$(MAKE) patch-kuadrant-operator-env
	@echo "All operators deployed in $(KUADRANT_NAMESPACE)"