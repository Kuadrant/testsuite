
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
ifeq ($(KUADRANT_OPERATOR_VERSION),latest)
	helm install kuadrant-operator kuadrant/kuadrant-operator --create-namespace --namespace $(KUADRANT_NAMESPACE) --wait --timeout=$(HELM_TIMEOUT)
else
	helm install kuadrant-operator kuadrant/kuadrant-operator --version $(KUADRANT_OPERATOR_VERSION) --create-namespace --namespace $(KUADRANT_NAMESPACE) --wait --timeout=$(HELM_TIMEOUT)
endif
	$(MAKE) patch-kuadrant-operator-env
	@echo "Kuadrant Operator $(KUADRANT_OPERATOR_VERSION) installed from Helm"
endif
	$(MAKE) patch-kuadrant-operator-image
ifeq ($(INSTALL_TRACING),true)
	@echo "Configuring OTEL tracing on limitador-operator..."
	@kubectl set env deployment/limitador-operator-controller-manager \
		-n $(KUADRANT_NAMESPACE) \
		OTEL_EXPORTER_OTLP_ENDPOINT=$(JAEGER_COLLECTOR_ENDPOINT) \
		OTEL_EXPORTER_OTLP_INSECURE=true
	@kubectl rollout status deployment/limitador-operator-controller-manager \
		-n $(KUADRANT_NAMESPACE) --timeout=$(KUBECTL_TIMEOUT)
endif

.PHONY: patch-kuadrant-operator-image
patch-kuadrant-operator-image: ## Patch Kuadrant Operator deployment with custom image
ifneq ($(KUADRANT_OPERATOR_IMAGE),)
	@echo "Patching Kuadrant Operator image to $(KUADRANT_OPERATOR_IMAGE)..."
	kubectl set image deployment/kuadrant-operator-controller-manager \
		-n $(KUADRANT_NAMESPACE) \
		manager=$(KUADRANT_OPERATOR_IMAGE)
	kubectl -n $(KUADRANT_NAMESPACE) rollout status deployment/kuadrant-operator-controller-manager --timeout=$(KUBECTL_TIMEOUT)
	@echo "Kuadrant Operator image patched"
else
	@echo "No custom operator image specified (KUADRANT_OPERATOR_IMAGE not set), skipping"
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
deploy-kuadrant-cr: ## Deploy Kuadrant CR (composed from INSTALL_PROMETHEUS and INSTALL_TRACING flags)
	@echo "Creating Kuadrant CR..."
	@{ \
		echo 'apiVersion: kuadrant.io/v1beta1'; \
		echo 'kind: Kuadrant'; \
		echo 'metadata:'; \
		echo '  name: kuadrant-sample'; \
		echo '  namespace: $(KUADRANT_NAMESPACE)'; \
		echo 'spec:'; \
		echo '  observability:'; \
		echo '    enable: $(INSTALL_PROMETHEUS)'; \
		if [ "$(INSTALL_TRACING)" = "true" ]; then \
			echo '    dataPlane:'; \
			echo '      defaultLevels:'; \
			echo '      - debug: "true"'; \
			echo '      httpHeaderIdentifier: x-request-id'; \
			echo '    tracing:'; \
			echo '      defaultEndpoint: "$(JAEGER_COLLECTOR_ENDPOINT)"'; \
			echo '      insecure: true'; \
		fi; \
	} | kubectl apply -f -
	kubectl wait kuadrant/kuadrant-sample --for=condition=Ready=True -n $(KUADRANT_NAMESPACE) --timeout=$(KUADRANT_CR_TIMEOUT)
	@echo "Kuadrant CR ready"

.PHONY: deploy-extensions
deploy-extensions: ## Deploy Kuadrant extensions (init container + manifests)
	@if [ ! -f "$(EXTENSIONS_MANIFESTS)" ]; then \
		echo "ERROR: Extensions manifest file not found: $(EXTENSIONS_MANIFESTS)"; \
		echo "Create the file or set EXTENSIONS_MANIFESTS to a valid path."; \
		exit 1; \
	fi
	@echo "Applying extension manifests from $(EXTENSIONS_MANIFESTS)..."
	kubectl apply -f $(EXTENSIONS_MANIFESTS)
	@echo "Patching kuadrant-operator-controller-manager with extensions init container..."
	kubectl patch deployment kuadrant-operator-controller-manager \
		-n $(KUADRANT_NAMESPACE) --type=strategic -p='{ \
		"spec": {"template": {"spec": { \
		  "volumes": [{"name": "extensions-binary-volume", "emptyDir": {}}], \
		  "containers": [{"name": "manager", \
		    "volumeMounts": [{"mountPath": "/extensions", "name": "extensions-binary-volume"}]}], \
		  "initContainers": [{"name": "copy-extensions", \
		    "command": ["cp", "-r", "/extensions/.", "/export"], \
		    "image": "$(EXTENSIONS_IMAGE)", \
		    "imagePullPolicy": "Always", \
		    "volumeMounts": [{"mountPath": "/export", "name": "extensions-binary-volume"}]}] \
		}}}}'
	@echo "Waiting for operator rollout..."
	kubectl -n $(KUADRANT_NAMESPACE) rollout status deployment/kuadrant-operator-controller-manager --timeout=$(KUBECTL_TIMEOUT)
	@echo "Extensions deployed successfully"
