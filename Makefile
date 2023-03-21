.PHONY: commit-acceptance pylint mypy clean \
	test glbc pipenv pipenv-dev container-image \

TB ?= short
LOGLEVEL ?= INFO

ifdef WORKSPACE  # Yes, this is for jenkins
resultsdir = $(WORKSPACE)
else
resultsdir ?= .
endif

PIPENV_VERBOSITY ?= -1
PIPENV_IGNORE_VIRTUALENVS ?= 1

PYTEST = pipenv run python -m pytest --tb=$(TB)

ifdef junit
PYTEST += --junitxml=$(resultsdir)/junit-$(@F).xml -o junit_suite_name=$(@F)
endif

ifdef html
PYTEST += --html=$(resultsdir)/report-$(@F).html
endif

commit-acceptance: black pylint mypy all-is-package

pylint mypy: pipenv-dev
	pipenv run $@ $(flags) testsuite

black: pipenv-dev
	pipenv run black --line-length 120 --check testsuite --diff

reformat:
	pipenv run black --line-length 120 testsuite

all-is-package:
	@echo
	@echo "Searching for dirs missing __init__.py"
	@! find testsuite/ -type d \! -name __pycache__ \! -path 'testsuite/resources/*' \! -exec test -e {}/__init__.py \; -print | grep '^..*$$'

# pattern to run individual testfile or all testfiles in directory
testsuite/%: FORCE pipenv
	$(PYTEST) --performance --glbc -v $(flags) $@

test: ## Run test
test pytest tests: pipenv
	$(PYTEST) -n4 -m 'not flaky' --dist loadfile $(flags) testsuite

# Run performance tests
performance: pipenv
	$(PYTEST) --performance $(flags) testsuite/tests/kuadrant/authorino/performance

glbc: ## Run glbc tests
glbc: pipenv
	$(PYTEST) --glbc $(flags) testsuite/tests/glbc

Pipfile.lock: Pipfile
	pipenv lock

.make-pipenv-sync: Pipfile.lock
	pipenv sync
	touch .make-pipenv-sync

.make-pipenv-sync-dev: Pipfile.lock
	pipenv sync --dev
	touch .make-pipenv-sync-dev .make-pipenv-sync

pipenv: .make-pipenv-sync

pipenv-dev: .make-pipenv-sync-dev

clean: ## clean pip deps
clean: mostlyclean
	rm -f Pipfile.lock

mostlyclean:
	rm -f .make-*
	rm -rf .mypy_cache
	-pipenv --rm

fake-sync:
	test -e Pipfile.lock \
		&& touch Pipfile.lock \
		&& touch .make-pipenv-sync .make-pipenv-sync-dev \
		|| true

# Check http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## Print this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# this ensures dependent target is run everytime
FORCE:
