
##@ Core Dependencies

.PHONY: install-metrics-server
install-metrics-server: ## Install metrics-server
	@echo "Installing metrics-server..."
	kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
	kubectl patch deployment metrics-server -n kube-system --type=json -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
	@echo "✅ metrics-server installed"

.PHONY: install-metallb
install-metallb: ## Install MetalLB for LoadBalancer services
	@echo "Installing MetalLB $(METALLB_VERSION)..."
	kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/$(METALLB_VERSION)/config/manifests/metallb-native.yaml
	kubectl wait --namespace metallb-system --for=condition=Available deployment/controller --timeout=$(METALLB_TIMEOUT)
	kubectl wait --namespace metallb-system --for=condition=ready pod --selector=component=controller --timeout=$(METALLB_TIMEOUT)
	@echo "Configuring MetalLB IP pool..."
	@printf '%s\n' \
		'apiVersion: metallb.io/v1beta1' \
		'kind: IPAddressPool' \
		'metadata:' \
		'  name: default' \
		'  namespace: metallb-system' \
		'spec:' \
		'  addresses:' \
		'  - 172.18.255.200-172.18.255.250' \
		| kubectl apply -f -
	@printf '%s\n' \
		'apiVersion: metallb.io/v1beta1' \
		'kind: L2Advertisement' \
		'metadata:' \
		'  name: default' \
		'  namespace: metallb-system' \
		| kubectl apply -f -
	@echo "✅ MetalLB installed with IP pool 172.18.255.200-172.18.255.250"

.PHONY: gateway-api-install
gateway-api-install: ## Install Gateway API CRDs
	@echo "Installing Gateway API $(GATEWAY_API_VERSION)..."
	kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/$(GATEWAY_API_VERSION)/standard-install.yaml
	@echo "✅ Gateway API CRDs installed"

.PHONY: install-cert-manager
install-cert-manager: ## Install cert-manager
	@echo "Installing cert-manager $(CERT_MANAGER_VERSION)..."
	kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/$(CERT_MANAGER_VERSION)/cert-manager.yaml
	kubectl wait --namespace cert-manager --for=condition=Available deployment/cert-manager --timeout=$(CERT_MANAGER_TIMEOUT)
	kubectl wait --namespace cert-manager --for=condition=Available deployment/cert-manager-webhook --timeout=$(CERT_MANAGER_TIMEOUT)
	kubectl wait --namespace cert-manager --for=condition=ready pod --selector=app.kubernetes.io/name=webhook --timeout=$(CERT_MANAGER_TIMEOUT)
	@echo "✅ cert-manager installed"

.PHONY: create-cluster-issuer
create-cluster-issuer: ## Create self-signed ClusterIssuer for TLS testing
	@echo "Creating self-signed ClusterIssuer..."
	@printf '%s\n' \
		'apiVersion: cert-manager.io/v1' \
		'kind: ClusterIssuer' \
		'metadata:' \
		'  name: kuadrant-qe-issuer' \
		'spec:' \
		'  selfSigned: {}' \
		| kubectl apply -f -
	@echo "✅ ClusterIssuer 'kuadrant-qe-issuer' created"

.PHONY: create-aws-credentials
create-aws-credentials: ## Create AWS credentials secret for DNS testing (only if credentials provided)
	@if [ -n "$(AWS_ACCESS_KEY_ID)" ] && [ -n "$(AWS_SECRET_ACCESS_KEY)" ] && [ -n "$(AWS_REGION)" ] && [ -n "$(AWS_BASE_DOMAIN)" ]; then \
		echo "Creating AWS credentials secret..."; \
		printf '%s\n' \
			'apiVersion: v1' \
			'kind: Secret' \
			'metadata:' \
			'  name: aws-credentials' \
			'  namespace: kuadrant' \
			'  annotations:' \
			'    base_domain: $(AWS_BASE_DOMAIN)' \
			'stringData:' \
			'  AWS_ACCESS_KEY_ID: $(AWS_ACCESS_KEY_ID)' \
			'  AWS_REGION: $(AWS_REGION)' \
			'  AWS_SECRET_ACCESS_KEY: $(AWS_SECRET_ACCESS_KEY)' \
			'type: kuadrant.io/aws' \
			| kubectl apply -f -; \
		echo "✅ AWS credentials secret created in kuadrant namespace"; \
	else \
		echo "⏭️  Skipping AWS credentials secret (requires AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, and AWS_BASE_DOMAIN)"; \
	fi