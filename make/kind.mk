
##@ Kind Cluster

.PHONY: kind-create-cluster
kind-create-cluster: ## Create kind cluster
	@echo "Creating kind cluster '$(KIND_CLUSTER_NAME)'..."
	@KIND_EXPERIMENTAL_PROVIDER=$(CONTAINER_ENGINE) kind create cluster --name $(KIND_CLUSTER_NAME) || echo "Cluster already exists"

.PHONY: kind-delete-cluster
kind-delete-cluster: ## Delete kind cluster
	@echo "Deleting kind cluster '$(KIND_CLUSTER_NAME)'..."
	@kind delete cluster --name $(KIND_CLUSTER_NAME) || true
