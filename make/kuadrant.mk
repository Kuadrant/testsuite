
##@ Kuadrant

.PHONY: create-test-namespaces
create-test-namespaces: ## Create namespaces for testing
	@echo "Creating test namespaces..."
	kubectl create namespace kuadrant || true
	kubectl create namespace kuadrant2 || true
	@echo "✅ Test namespaces created"

.PHONY: deploy-kuadrant-operator
deploy-kuadrant-operator: ## Deploy Kuadrant Operator (via Helm by default, or custom image)
ifneq ($(KUADRANT_OPERATOR_IMAGE),)
	@echo "Installing Kuadrant Operator from custom image: $(KUADRANT_OPERATOR_IMAGE)"
	$(MAKE) deploy-kuadrant-operator-local
else
	@echo "Installing Kuadrant Operator $(KUADRANT_OPERATOR_VERSION) from Helm..."
	helm repo add kuadrant https://kuadrant.io/helm-charts/ --force-update
	$(if $(filter latest,$(KUADRANT_OPERATOR_VERSION)), \
		helm install kuadrant-operator kuadrant/kuadrant-operator --create-namespace --namespace $(KUADRANT_NAMESPACE), \
		helm install kuadrant-operator kuadrant/kuadrant-operator --version $(KUADRANT_OPERATOR_VERSION) --create-namespace --namespace $(KUADRANT_NAMESPACE))
	kubectl -n $(KUADRANT_NAMESPACE) wait --timeout=$(KUBECTL_TIMEOUT) --for=condition=Available deployments --all
	@echo "✅ Kuadrant Operator $(KUADRANT_OPERATOR_VERSION) installed"
endif

.PHONY: deploy-kuadrant-operator-local
deploy-kuadrant-operator-local: ## Deploy Kuadrant Operator from local build/image
	@if [ -z "$(KUADRANT_OPERATOR_IMAGE)" ]; then \
		echo "ERROR: KUADRANT_OPERATOR_IMAGE not set"; \
		echo "Set KUADRANT_OPERATOR_IMAGE=your-image:tag"; \
		exit 1; \
	fi
	@echo "Loading image into kind cluster..."
	kind load docker-image $(KUADRANT_OPERATOR_IMAGE) --name $(KIND_CLUSTER_NAME)
	@echo "Deploying operator with image $(KUADRANT_OPERATOR_IMAGE)..."
	kubectl create namespace $(KUADRANT_NAMESPACE) || true
	kubectl apply -k https://github.com/kuadrant/kuadrant-operator/config/crd
	@if [ ! -d "/tmp/kuadrant-operator-deploy" ]; then \
		cd /tmp && git clone --depth=1 https://github.com/kuadrant/kuadrant-operator.git kuadrant-operator-deploy; \
	else \
		cd /tmp/kuadrant-operator-deploy && git pull; \
	fi
	cd /tmp/kuadrant-operator-deploy/config/manager && \
		kustomize edit set image controller=$(KUADRANT_OPERATOR_IMAGE) && \
		kustomize build ../deploy | kubectl apply --server-side -f -
	kubectl -n $(KUADRANT_NAMESPACE) wait --timeout=$(KUBECTL_TIMEOUT) --for=condition=Available deployments --all
	@echo "✅ Kuadrant Operator deployed from image $(KUADRANT_OPERATOR_IMAGE)"

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
	@echo "✅ Kuadrant CR ready"