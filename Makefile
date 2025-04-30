.PHONY: commit-acceptance pylint mypy black reformat test authorino poetry poetry-no-dev mgc container-image polish-junit reportportal authorino-standalone limitador kuadrant kuadrant-only disruptive kuadrantctl multicluster

TB ?= short
LOGLEVEL ?= INFO

ifdef WORKSPACE  # Yes, this is for jenkins
resultsdir = $(WORKSPACE)
else
resultsdir ?= .
endif

PYTEST = poetry run python -m pytest --tb=$(TB) -o cache_dir=$(resultsdir)/.pytest_cache.$(@F)
RUNSCRIPT = poetry run ./scripts/

ifdef junit
PYTEST += --junitxml=$(resultsdir)/junit-$(@F).xml -o junit_suite_name=$(@F)
endif

ifdef html
PYTEST += --html=$(resultsdir)/report-$(@F).html --self-contained-html
endif

commit-acceptance: black pylint mypy ## Runs pre-commit linting checks

pylint mypy: poetry
	poetry run $@ $(flags) testsuite

black: poetry
	poetry run black --check testsuite --diff

reformat: poetry  ## Reformats testsuite with black
	poetry run black testsuite

# pattern to run individual testfile or all testfiles in directory
testsuite/%: FORCE poetry-no-dev
	$(PYTEST) -v $(flags) $@

test: ## Run all non mgc tests
test pytest tests: kuadrant

smoke: poetry-no-dev
	$(PYTEST) -n4 -m 'smoke' --dist loadfile --enforce $(flags) testsuite/tests

authorino: ## Run only authorino related tests
authorino: poetry-no-dev
	$(PYTEST) -n4 -m 'authorino and not multicluster' --dist loadfile --enforce $(flags) testsuite/tests/singlecluster

authorino-standalone: ## Run only test capable of running with standalone Authorino
authorino-standalone: poetry-no-dev
	$(PYTEST) -n4 -m 'authorino and not kuadrant_only' --dist loadfile --enforce --standalone $(flags) testsuite/tests/singlecluster/authorino

limitador: ## Run only Limitador related tests
limitador: poetry-no-dev
	$(PYTEST) -n4 -m 'limitador and not multicluster' --dist loadfile --enforce $(flags) testsuite/tests/singlecluster

kuadrant: ## Run all tests available on Kuadrant
kuadrant: poetry-no-dev
	$(PYTEST) -n4 -m 'not standalone_only and not multicluster and not disruptive' --dist loadfile --enforce $(flags) testsuite/tests/singlecluster

kuadrant-only: ## Run Kuadrant-only tests
kuadrant-only: poetry-no-dev
	$(PYTEST) -n4 -m 'kuadrant_only and not standalone_only and not disruptive and not multicluster' --dist loadfile --enforce $(flags) testsuite/tests/singlecluster

multicluster: ## Run Multicluster only tests
multicluster: poetry-no-dev
	$(PYTEST) -n2 -m 'multicluster' --dist loadfile --enforce $(flags) testsuite

dnstls: ## Run DNS and TLS tests
dnstls: poetry-no-dev
	$(PYTEST) -n4 -m 'dnspolicy or tlspolicy' --dist loadfile --enforce $(flags) testsuite

disruptive: ## Run disruptive tests
disruptive: poetry-no-dev
	$(PYTEST) -m 'disruptive' $(flags) testsuite

kuadrantctl: ## Run Kuadrantctl tests
kuadrantctl: poetry-no-dev
	$(PYTEST) -n4 --dist loadfile --enforce $(flags) testsuite/tests/kuadrantctl

poetry.lock: pyproject.toml
	poetry lock

.make-poetry-sync: poetry.lock
	@if [ -z "$(poetry env list)" -o -n "${force}" ]; then poetry install --sync; fi
	@ touch .make-poetry-sync .make-poetry-sync-no-dev

.make-poetry-sync-no-dev: poetry.lock
	@if [ -z "$(poetry env list)" -o -n "${force}" ]; then poetry install --sync --without dev; fi
	@ touch .make-poetry-sync-no-dev


poetry: .make-poetry-sync ## Installs poetry with all dependencies

poetry-no-dev: .make-poetry-sync-no-dev ## Installs poetry without development dependencies

polish-junit: ## Remove skipped tests and logs from passing tests
polish-junit:
	gzip -f $(resultsdir)/junit-*.xml
	# 'cat' on next line is neessary to avoid wipe of the files
	for file in $(resultsdir)/junit-*.xml.gz; do zcat $$file | $(RUNSCRIPT)xslt-apply ./xslt/polish-junit.xsl >$${file%.gz}; done  # bashism!!!
	# this deletes something it didn't create, dangerous!!!
	-rm -f $(resultsdir)/junit-*.xml.gz

reportportal: ## Upload results to reportportal. Appropriate variables for juni2reportportal must be set
reportportal: polish-junit
	$(RUNSCRIPT)junit2reportportal $(resultsdir)/junit-*.xml

.PHONY: help
help: ## Display this help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

CR_NAMES = $\
authorinos.operator.authorino.kuadrant.io,$\
gateways.networking.istio.io,$\
gateways.gateway.networking.k8s.io,$\
httproutes.gateway.networking.k8s.io,$\
deployments.apps,$\
services,$\
serviceaccounts,$\
secrets,$\
authconfigs.authorino.kuadrant.io,$\
authpolicies.kuadrant.io,$\
ratelimitpolicies.kuadrant.io,$\
dnspolicies.kuadrant.io,$\
tlspolicies.kuadrant.io,$\
validatingwebhookconfigurations.admissionregistration.k8s.io,$\
wasmplugins.extensions.istio.io,$\
servicemonitors.monitoring.coreos.com,$\
podmonitors.monitoring.coreos.com

clean: ## Clean all objects on cluster created by running this testsuite. Set the env variable USER to delete after someone else
	@echo "Deleting objects for user: $(USER)"
	@test -n "$(USER)"  # exit if $$USER is empty
	@if kubectl api-resources -o name | grep "routes.route.openshift.io" > /dev/null; then \
	CR="$(CR_NAMES),routes.route.openshift.io"; \
	else \
	CR="$(CR_NAMES)"; \
	fi; \
	kubectl get --chunk-size=0 -n kuadrant -o name "$$CR" \
	| grep "$(USER)" \
	| xargs --no-run-if-empty -P 20 -n 1 kubectl delete --ignore-not-found -n kuadrant
# this ensures dependent target is run everytime
FORCE:

##@ Scale Testing

.PHONY: test-scale-dnspolicy
test-scale-dnspolicy: export DNS_OPERATOR_GITHUB_ORG := kuadrant
test-scale-dnspolicy: export DNS_OPERATOR_GITREF := main
test-scale-dnspolicy: export JOB_ITERATIONS := 1
test-scale-dnspolicy: export KUADRANT_ZONE_ROOT_DOMAIN := kuadrant.local
test-scale-dnspolicy: export DNS_PROVIDER := inmemory
test-scale-dnspolicy: export PROMETHEUS_URL := http://127.0.0.1:9090
test-scale-dnspolicy: export PROMETHEUS_TOKEN := ""
test-scale-dnspolicy: export SKIP_CLEANUP := false
test-scale-dnspolicy: export NUM_GWS := 1
test-scale-dnspolicy: export NUM_LISTENERS := 1
test-scale-dnspolicy: KUBEBURNER_WORKLOAD := namespaced-dns-operator-deployments.yaml
test-scale-dnspolicy: kube-burner ## Run DNSPolicy scale tests.
	@echo "test-scale-dnspolicy: KUBEBURNER_WORKLOAD=${KUBEBURNER_WORKLOAD} JOB_ITERATIONS=${JOB_ITERATIONS} KUADRANT_ZONE_ROOT_DOMAIN=${KUADRANT_ZONE_ROOT_DOMAIN} DNS_PROVIDER=${DNS_PROVIDER} PROMETHEUS_URL=${PROMETHEUS_URL} PROMETHEUS_TOKEN=${PROMETHEUS_TOKEN}"
	cd scale_test/dnspolicy && $(KUBE_BURNER) init -c ${KUBEBURNER_WORKLOAD} --log-level debug

##@ Build Dependencies

## Location to install dependencies to
LOCALBIN ?= $(shell pwd)/bin
$(LOCALBIN):
	mkdir -p $(LOCALBIN)

## Tool Binaries
KUBE_BURNER ?= $(LOCALBIN)/kube-burner

## Tool Versions
KUBE_BURNER_VERSION = v1.11.1

.PHONY: kube-burner
kube-burner: $(KUBE_BURNER) ## Download kube-burner locally if necessary.
$(KUBE_BURNER):
	@{ \
	set -e ;\
	mkdir -p $(dir $(KUBE_BURNER)) ;\
	OS=$(shell go env GOOS) && ARCH=$(shell go env GOARCH) && \
	wget -O kube-burner.tar.gz https://github.com/kube-burner/kube-burner/releases/download/v1.11.1/kube-burner-V1.11.1-linux-x86_64.tar.gz ;\
	tar -zxvf kube-burner.tar.gz ;\
	mv kube-burner $(KUBE_BURNER) ;\
	chmod +x $(KUBE_BURNER) ;\
	rm -rf $${OS}-$${ARCH} kube-burner.tar.gz ;\
	}
