.PHONY: commit-acceptance pylint mypy black reformat test authorino poetry poetry-no-dev mgc container-image polish-junit reportportal authorino-standalone limitador kuadrant kuadrant-only disruptive kuadrantctl multicluster ui playwright-install

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


##@ Single-cluster Testing

# pattern to run individual testfile or all testfiles in directory
testsuite/%: FORCE poetry-no-dev
	$(PYTEST) -v $(flags) $@

test pytest tests singlecluster: kuadrant  ## Run all single-cluster tests

smoke: poetry-no-dev  ## Run a small amount of selected tests to verify basic functionality
	$(PYTEST) -n4 -m 'smoke' --dist loadfile --enforce $(flags) testsuite/tests/

kuadrant: poetry-no-dev  ## Run all tests available on Kuadrant
	$(PYTEST) -n4 -m 'not standalone_only and not disruptive and not ui' --dist loadfile --enforce $(flags) testsuite/tests/singlecluster

authorino: poetry-no-dev  ## Run only Authorino related tests
	$(PYTEST) -n4 -m 'authorino and not disruptive' --dist loadfile --enforce $(flags) testsuite/tests/singlecluster/

authorino-standalone: poetry-no-dev  ## Run only test capable of running with standalone Authorino
	$(PYTEST) -n4 -m 'authorino and not kuadrant_only and not disruptive' --dist loadfile --enforce --standalone $(flags) testsuite/tests/singlecluster/authorino/

limitador: poetry-no-dev  ## Run only Limitador related tests
	$(PYTEST) -n4 -m 'limitador and not disruptive' --dist loadfile --enforce $(flags) testsuite/tests/singlecluster/

dnstls: poetry-no-dev  ## Run DNS and TLS tests
	$(PYTEST) -n4 -m '(dnspolicy or tlspolicy) and not disruptive' --dist loadfile --enforce $(flags) testsuite/tests/singlecluster/

extensions: poetry-no-dev  ## Run extensions tests
	$(PYTEST) -n4 -m 'extensions and not disruptive' --dist loadfile --enforce $(flags) testsuite/tests/singlecluster/

observability: poetry-no-dev  ## Run metrics, tracing and logging tests (add `flags=--standalone` to only run tests capable of running with standalone Authorino)
	$(PYTEST) -n4 -m 'observability and not disruptive' --dist loadfile $(flags) testsuite/tests/singlecluster/

defaults_overrides: poetry-no-dev  ## Run Defaults and Overrides tests
	$(PYTEST) -n4 -m 'defaults_overrides and not disruptive' --dist loadfile --enforce $(flags) testsuite/tests/singlecluster/

ui: playwright-install ## Run UI (console plugin) tests
	$(PYTEST) -n4 -m 'ui' --dist loadfile --enforce $(flags) testsuite/tests/singlecluster/ui/

disruptive: poetry-no-dev  ## Run disruptive tests
	$(PYTEST) -m 'disruptive' $(flags) testsuite/tests/

kuadrantctl: poetry-no-dev  ## Run Kuadrantctl tests
	$(PYTEST) -n4 --dist loadfile --enforce $(flags) testsuite/tests/kuadrantctl/

##@ Multi-cluster Testing

multicluster: poetry-no-dev  ## Run Multicluster only tests
	$(PYTEST) -n2 -m 'multicluster' --dist loadfile --enforce $(flags) testsuite/tests/multicluster/

coredns_one_primary: poetry-no-dev  ## Run coredns one primary tests
	$(PYTEST) -n1 -m 'coredns_one_primary' --dist loadfile --enforce $(flags) testsuite/tests/multicluster/coredns/

coredns_two_primaries: poetry-no-dev  ## Run coredns two primary tests
	$(PYTEST) -n1 -m 'coredns_two_primaries' --dist loadfile --enforce $(flags) testsuite/tests/multicluster/coredns/


##@ Local Development

local-env-setup:  ## Create local KIND cluster with full Kuadrant setup (replicates CI environment)
	./bin/setup-ci-env.sh

local-env-setup-minimal:  ## Create local KIND cluster without testsuite tools (faster setup)
	./bin/setup-ci-env.sh --skip-tools

local-env-status:  ## Check status of local environment
	./bin/setup-ci-env.sh --status

local-env-cleanup:  ## Delete local KIND cluster
	./bin/setup-ci-env.sh --cleanup

##@ Misc

commit-acceptance: black pylint mypy  ## Runs pre-commit linting checks

pylint mypy: poetry  ## Checks testsuite formatting with pylint/mypy
	poetry run $@ $(flags) testsuite

black: poetry  ## Checks testsuite formatting with Black
	poetry run black --check testsuite --diff

reformat: poetry  ## Reformats testsuite with black
	poetry run black testsuite

polish-junit:  ## Remove skipped tests and logs from passing tests
	@if ls $(resultsdir)/junit-*.xml >/dev/null 2>&1; then \
	   gzip -f $(resultsdir)/junit-*.xml; \
	   for file in $(resultsdir)/junit-*.xml.gz; do \
	      if [ -f "$$file" ]; then \
	         gunzip -c "$$file" | $(RUNSCRIPT)xslt-apply ./xslt/polish-junit.xsl > "$${file%.gz}"; \
	      fi; \
	   done; \
	   rm -f $(resultsdir)/junit-*.xml.gz; \
	else \
	   echo "No junit XML files found in $(resultsdir)"; \
	   exit 1; \
	fi

reportportal: polish-junit  ## Upload results to reportportal. Appropriate variables for juni2reportportal must be set
	$(RUNSCRIPT)junit2reportportal $(resultsdir)/junit-*.xml

.PHONY: help
help: ## Display this help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

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
podmonitors.monitoring.coreos.com,$\
apiservices.apiregistration.k8s.io,$\
horizontalpodautoscalers.autoscaling,$\
oidcpolicies.extensions.kuadrant.io,$\
planpolicies.extensions.kuadrant.io

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


##@ Dependency Management

poetry.lock: pyproject.toml
	poetry lock

.make-poetry-sync: poetry.lock
	@if [ -z "$(poetry env list)" -o -n "${force}" ]; then poetry sync; fi
	@ touch .make-poetry-sync .make-poetry-sync-no-dev

.make-poetry-sync-no-dev: poetry.lock
	@if [ -z "$(poetry env list)" -o -n "${force}" ]; then poetry sync --without dev; fi
	@ touch .make-poetry-sync-no-dev

.make-playwright-install: .make-poetry-sync-no-dev
	@echo "Installing Playwright browsers..."
	@poetry run playwright install --with-deps
	@touch .make-playwright-install

poetry: .make-poetry-sync ## Installs poetry with all dependencies

poetry-no-dev: .make-poetry-sync-no-dev ## Installs poetry without development dependencies

playwright-install: .make-playwright-install ## Install Playwright browser binaries

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
test-scale-dnspolicy: KUBEBURNER_WORKLOAD := namespaced-dns-operator-deployments-config.yaml
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
	wget -O kube-burner.tar.gz https://github.com/kube-burner/kube-burner/releases/download/v1.16.1/kube-burner-V1.16.1-linux-x86_64.tar.gz ;\
	tar -zxvf kube-burner.tar.gz ;\
	mv kube-burner $(KUBE_BURNER) ;\
	chmod +x $(KUBE_BURNER) ;\
	rm -rf $${OS}-$${ARCH} kube-burner.tar.gz ;\
	}

# this ensures dependent target is run everytime
FORCE:
