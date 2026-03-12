
##@ Istio

.PHONY: istio-install
istio-install: ## Install Istio via SAIL operator
	@echo "Installing Sail Operator $(SAIL_OPERATOR_VERSION)..."
	helm repo add sail-operator https://istio-ecosystem.github.io/sail-operator --force-update
	helm install sail-operator \
		--create-namespace \
		--namespace istio-system \
		--wait \
		--timeout=$(HELM_TIMEOUT) \
		sail-operator/sail-operator \
		--version $(SAIL_OPERATOR_VERSION)
	@echo "Creating Istio CR..."
	@printf '%s\n' \
		'apiVersion: sailoperator.io/v1' \
		'kind: Istio' \
		'metadata:' \
		'  name: default' \
		'spec:' \
		'  namespace: istio-system' \
		'  updateStrategy:' \
		'    type: InPlace' \
		'  values:' \
		'    pilot:' \
		'      autoscaleMin: 2' \
		'  version: $(ISTIO_VERSION)' \
		| kubectl apply -f -
	@echo "Istio $(ISTIO_VERSION) installed via SAIL"
