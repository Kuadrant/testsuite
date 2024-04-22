.PHONY: commit-acceptance pylint mypy black reformat test performance authorino poetry poetry-no-dev mgc container-image polish-junit reportportal authorino-standalone limitador kuadrant kuadrant-only

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
PYTEST += --html=$(resultsdir)/report-$(@F).html
endif

commit-acceptance: black pylint mypy all-is-package ## Runs pre-commit linting checks

pylint mypy: poetry
	poetry run $@ $(flags) testsuite

black: poetry
	poetry run black --check testsuite --diff

reformat: poetry  ## Reformats testsuite with black
	poetry run black testsuite

all-is-package:
	@echo
	@echo "Searching for dirs missing __init__.py"
	@! find testsuite/ -type d \! -name __pycache__ \! -path 'testsuite/resources/*' \! -exec test -e {}/__init__.py \; -print | grep '^..*$$'

# pattern to run individual testfile or all testfiles in directory
testsuite/%: FORCE poetry-no-dev
	$(PYTEST) --performance -v $(flags) $@

test: ## Run all non mgc tests
test pytest tests: kuadrant

authorino: ## Run only authorino related tests
authorino: poetry-no-dev
	$(PYTEST) -n4 -m 'authorino' --dist loadfile --enforce $(flags) testsuite

authorino-standalone: ## Run only test capable of running with standalone Authorino
authorino-standalone: poetry-no-dev
	$(PYTEST) -n4 -m 'authorino and not kuadrant_only' --runxfail --dist loadfile --enforce --standalone $(flags) testsuite/tests/kuadrant/authorino

limitador: ## Run only Limitador related tests
limitador: poetry-no-dev
	$(PYTEST) -n4 -m 'limitador' --dist loadfile --enforce $(flags) testsuite

kuadrant: ## Run all tests available on Kuadrant
kuadrant: poetry-no-dev
	$(PYTEST) -n4 -m 'not standalone_only' --dist loadfile --enforce $(flags) testsuite

kuadrant-only: ## Run Kuadrant-only tests
kuadrant-only: poetry-no-dev
	$(PYTEST) -n4 -m 'kuadrant_only and not standalone_only' --dist loadfile --enforce $(flags) testsuite

performance: ## Run performance tests
performance: poetry-no-dev
	$(PYTEST) --performance $(flags) testsuite/tests/kuadrant/authorino/performance

poetry.lock: pyproject.toml
	poetry lock

.make-poetry-sync: poetry.lock
	@if [ -z "$(poetry env list)" -o -n "${force}" ]; then poetry install --sync --no-root; fi
	@ touch .make-poetry-sync .make-poetry-sync-no-dev

.make-poetry-sync-no-dev: poetry.lock
	@if [ -z "$(poetry env list)" -o -n "${force}" ]; then poetry install --sync --no-root --without dev; fi
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

# Check http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## Print this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

CR_NAMES = "$\
Gateway,$\
HTTPRoute,$\
Deployment,$\
Service,$\
Route,$\
ServiceAccount,$\
Secret,$\
AuthConfig,$\
AuthPolicy,$\
RateLimitPolicy,$\
DNSPolicy,$\
TLSPolicy,$\
Authorino,$\
WasmPlugin"

clean: ## Clean all objects in Openshift created by running this testsuite
	test -n "$(USER)"  # exit if $$USER is empty
	oc get --chunk-size=0 -n kuadrant -o name $(CR_NAMES) \
	| grep "$(USER)" \
	| xargs --no-run-if-empty -P 20 -n 1 oc delete --ignore-not-found -n kuadrant

# this ensures dependent target is run everytime
FORCE:
