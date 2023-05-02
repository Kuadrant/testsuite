.PHONY: commit-acceptance pylint mypy black reformat test poetry poetry-no-dev glbc container-image

TB ?= short
LOGLEVEL ?= INFO

ifdef WORKSPACE  # Yes, this is for jenkins
resultsdir = $(WORKSPACE)
else
resultsdir ?= .
endif

PYTEST = poetry run python -m pytest --tb=$(TB)

ifdef junit
PYTEST += --junitxml=$(resultsdir)/junit-$(@F).xml -o junit_suite_name=$(@F)
endif

ifdef html
PYTEST += --html=$(resultsdir)/report-$(@F).html
endif

commit-acceptance: black pylint mypy all-is-package

pylint mypy: poetry
	poetry run $@ $(flags) testsuite

black: poetry
	poetry run black --check testsuite --diff

reformat: poetry
	pipenv run black testsuite

all-is-package:
	@echo
	@echo "Searching for dirs missing __init__.py"
	@! find testsuite/ -type d \! -name __pycache__ \! -path 'testsuite/resources/*' \! -exec test -e {}/__init__.py \; -print | grep '^..*$$'

# pattern to run individual testfile or all testfiles in directory
testsuite/%: FORCE poetry-no-dev
	$(PYTEST) --performance --glbc -v $(flags) $@

test: ## Run test
test pytest tests: poetry-no-dev
	$(PYTEST) -n4 -m 'not flaky' --dist loadfile $(flags) testsuite

performance: ## Run performance tests
performance: poetry-no-dev
	$(PYTEST) --performance $(flags) testsuite/tests/kuadrant/authorino/performance

glbc: ## Run glbc tests
glbc: poetry-no-dev
	$(PYTEST) --glbc $(flags) testsuite/tests/glbc

poetry.lock: pyproject.toml
	poetry lock

.make-poetry-sync: poetry.lock
	@if ! poetry env list | grep ^; then poetry install --sync --no-root; fi
	@ touch .make-poetry-sync .make-poetry-sync-no-dev

.make-poetry-sync-no-dev: poetry.lock
	@if ! poetry env list | grep ^; then poetry install --sync --no-root --without dev; fi
	@ touch .make-poetry-sync-no-dev


poetry: .make-poetry-sync

poetry-no-dev: .make-poetry-sync-no-dev

# Check http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## Print this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# this ensures dependent target is run everytime
FORCE:
