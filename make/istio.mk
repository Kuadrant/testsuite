
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

.PHONY: configure-istio-tracing
configure-istio-tracing: ## Configure Istio for distributed tracing
	@echo "Configuring Istio for tracing with Jaeger..."
	@# Patch Istio CR to add tracing extension provider and JSON access logs
	@kubectl patch istio default -n istio-system --type=merge -p '{"spec":{"values":{"meshConfig":{"accessLogFile":"/dev/stdout","accessLogEncoding":"JSON","accessLogFormat":"{\"start_time\":\"%START_TIME%\",\"method\":\"%REQ(:METHOD)%\",\"path\":\"%REQ(X-ENVOY-ORIGINAL-PATH?:PATH)%\",\"protocol\":\"%PROTOCOL%\",\"response_code\":\"%RESPONSE_CODE%\",\"response_flags\":\"%RESPONSE_FLAGS%\",\"bytes_received\":\"%BYTES_RECEIVED%\",\"bytes_sent\":\"%BYTES_SENT%\",\"duration\":\"%DURATION%\",\"upstream_service_time\":\"%RESP(X-ENVOY-UPSTREAM-SERVICE-TIME)%\",\"x_forwarded_for\":\"%REQ(X-FORWARDED-FOR)%\",\"user_agent\":\"%REQ(USER-AGENT)%\",\"request_id\":\"%REQ(X-REQUEST-ID)%\",\"authority\":\"%REQ(:AUTHORITY)%\",\"upstream_host\":\"%UPSTREAM_HOST%\",\"upstream_cluster\":\"%UPSTREAM_CLUSTER%\",\"route_name\":\"%ROUTE_NAME%\"}","enableTracing":true,"defaultConfig":{"tracing":{}},"extensionProviders":[{"name":"jaeger-otlp","opentelemetry":{"port":4317,"service":"jaeger-collector.$(TOOLS_NAMESPACE).svc.cluster.local"}}]}}}}'
	@# Create Telemetry resource to enable tracing
	@printf '%s\n' \
		'apiVersion: telemetry.istio.io/v1' \
		'kind: Telemetry' \
		'metadata:' \
		'  name: default-telemetry' \
		'  namespace: istio-system' \
		'spec:' \
		'  tracing:' \
		'  - providers:' \
		'    - name: jaeger-otlp' \
		'    randomSamplingPercentage: 100' \
		| kubectl apply -f -
	@echo "Istio tracing configured"
