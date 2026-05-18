
##@ Kind Cluster

.PHONY: kind-create-cluster
kind-create-cluster: ## Create kind cluster
	@echo "Creating kind cluster '$(KIND_CLUSTER_NAME)'..."
	@if kind get clusters | grep -qx "$(KIND_CLUSTER_NAME)"; then \
		echo "Cluster already exists"; \
	else \
		KIND_EXPERIMENTAL_PROVIDER=$(CONTAINER_ENGINE) kind create cluster --name $(KIND_CLUSTER_NAME); \
	fi

.PHONY: kind-delete-cluster
kind-delete-cluster: ## Delete kind cluster
	@echo "Deleting kind cluster '$(KIND_CLUSTER_NAME)'..."
	@KIND_EXPERIMENTAL_PROVIDER=$(CONTAINER_ENGINE) kind delete cluster --name $(KIND_CLUSTER_NAME) || true
