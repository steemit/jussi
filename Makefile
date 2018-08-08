SHELL := /bin/bash
ROOT_DIR := $(shell pwd)

PROJECT_NAME := $(notdir $(ROOT_DIR))
PROJECT_DOCKER_TAG := steemit/$(PROJECT_NAME)
PROJECT_DOCKER_RUN_ARGS := -p8080:8080  -p7777:7777 --env-file .env -v $(shell pwd)/DEV_config.json:/app/DEV_config.json

PIPENV_VENV_IN_PROJECT := 1
export PIPENV_VENV_IN_PROJECT
PYTHON_VERSION := 3.6
PYTHON := $(shell which python$(PYTHON_VERSION))
ENVFILE := .env

.DEFAULT_GOAL := help


.PHONY: help
help:
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: init
init: clean ## install project requrements into .venv
	pip3 install --upgrade pipenv
	-pipenv --rm
	if [[ $(shell uname) == 'Darwin' ]]; then \
	brew install openssl; \
	env LDFLAGS="-L$(shell brew --prefix openssl)/lib" CFLAGS="-I$(shell brew --prefix openssl)/include" pipenv update --python $(PYTHON) --dev; \
	else \
		pipenv update --python $(PYTHON) --dev; \
	fi
	pipenv run pre-commit install

Pipfile.lock: Pipfile
	$(shell docker run $(PROJECT_DOCKER_TAG) /bin/bash -c 'pipenv lock && cat Pipfile.lock' > $@)

.PHONY: clean
clean: ## clean python and dev junk
	find . -name "__pycache__" | xargs rm -rf
	-rm -rf .cache
	-rm -rf .eggs
	-rm -rf .mypy_cache
	-rm -rf *.egg-info
	-rm -rf *.log
	-rm -rf service/*/supervise

.PHONY: build
build: clean clean-perf ## build docker image
	docker build -t $(PROJECT_DOCKER_TAG) .

.PHONY: run
run: ## run docker image
	docker run $(PROJECT_DOCKER_RUN_ARGS) $(PROJECT_DOCKER_TAG)

.PHONY: run-local
run-local: ## run the python app without docker
	pipenv run python3 -m jussi.serve  --server_workers=1 --upstream_config_file DEV_config.json

.PHONY: test
test: ## run all tests
	pipenv run pytest

.PHONY: test-with-docker
test-with-docker: Pipfile.lock build  ## run tests that depend on docker
	pipenv run pytest --rundocker --jussiurl http://localhost:8080

.PHONY: lint
lint: ## lint python files
	pipenv run pylint $(PROJECT_NAME)

.PHONY: fmt
fmt: ## format python files
    # yapf is disabled until the update 3.6 fstring compat
	#pipenv run yapf --in-place --style pep8 --recursive $(PROJECT_NAME)
	pipenv run autopep8 --verbose --verbose --max-line-length=100 --aggressive --jobs -1 --in-place  --recursive $(PROJECT_NAME) $(PROJECT_NAME)/tests

.PHONY: fix-imports
fix-imports: remove-unused-imports sort-imports ## remove unused and then sort imports

.PHONY: remove-unused-imports
remove-unused-imports: ## remove unused imports from python files
	pipenv run autoflake --in-place --remove-all-unused-imports --recursive $(PROJECT_NAME)

.PHONY: sort-imports
sort-imports: ## sorts python imports using isort with settings from .editorconfig
	pipenv run isort --verbose --recursive --atomic --settings-path  .isort.cfg --virtual-env .venv $(PROJECT_NAME)

.PHONY: pipenv-check
pipenv-check:
	pipenv check

.PHONY: pre-commit
pre-commit: ## run pre-commit against modified files
	pipenv run pre-commit run

.PHONY: pre-commit-all
pre-commit-all: ## run pre-commit against all files
	pipenv run pre-commit run --all-files

.PHONY: unmac
unmac:
	find $(ROOT_DIR) -type f -name '.DS_Store' -delete

.PHONY: prepare
prepare: fix-imports lint fmt pre-commit-all pipenv-check test unmac  ## fix-imports lint fmt pre-commit-all pipenv-check unmac test

.PHONY: prepare-without-test
prepare-without-test: fix-imports lint fmt pre-commit-all pipenv-check unmac ## fix-imports lint fmt pre-commit-all pipenv-check unmac

.PHONY: prepare-and-build
prepare-and-build: prepare-without-test test-with-docker  ## run all formatting and pre-commit checks, then build docker image

.PHONY: commit
commit: prepare-and-build
	git commit -a

.PHONY: mypy
mypy: ## run mypy type checking on python files
	pipenv run mypy --ignore-missing-imports --python-version $(PYTHON_VERSION) $(PROJECT_NAME)

.PHONY: 8080
8080:
	http :8080/
	http :8080/health
	http :8080/.well-known/healthcheck.json
	http --json :8080/ id=1 jsonrpc="2.0" method=get_block params:='[1000]'

.PHONY: 9000
9000:
	http :9000/
	http :9000/health
	http :9000/.well-known/healthcheck.json
	http --json :9000/ id:=1 jsonrpc=2.0 method=get_block params:='[1000]'


.PHONY: test-local-steemd-calls
test-local-steemd-calls:
	pipenv run pytest -vv tests/test_responses.py::test_steemd_responses --jussiurl http://localhost:9000

.PHONY: test-local-appbase-calls
test-local-appbase-calls:
	pipenv run pytest -vv tests/test_responses.py::test_appbase_responses --jussiurl http://localhost:9000

.PHONY: test-local-appbase-translation-calls
test-local-appbase-translation-calls:
	pipenv run pytest -vv tests/test_responses.py::test_appbase_translation_responses --jussiurl http://localhost:9000

.PHONY: test-live-dev-appbase-calls
test-live-dev-appbase-calls:
	pipenv run pytest -vv tests/test_responses.py::test_appbase_responses --jussiurl https://api.steemitdev.com

.PHONY: test-live-staging-appbase-calls
test-live-staging-appbase-calls:
	pipenv run pytest -vv tests/test_responses.py::test_appbase_responses --jussiurl https://api.steemitstage.com

.PHONY: test-live-prod-appbase-calls
test-live-prod-appbase-calls:
	pipenv run pytest --maxfail=1 tests/test_responses.py::test_appbase_responses --jussiurl https://api.steemit.com


./perf:
	mkdir $@

%.pstats: perf
	-pipenv run python -m cProfile -o $*.pstats ./jussi/serve.py --server_workers=1 --upstream_config_file DEV_config.json

%.png: %.pstats
	-pipenv run gprof2dot -f pstats $< | dot -Tpng -o $@

.PHONY: clean-perf
clean-perf: ## clean pstats and flamegraph svgs
	rm -rf $(ROOT_DIR)/perf

.PHONY: install-python-steem-macos
install-python-steem-macos: ## install steem-python lib on macos using homebrew's openssl
	env LDFLAGS="-L$(shell brew --prefix openssl)/lib" CFLAGS="-I$(shell brew --prefix openssl)/include" pipenv install steem
