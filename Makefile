SHELL := /bin/bash
ROOT_DIR := $(shell pwd)

PROJECT_NAME := $(notdir $(ROOT_DIR))
PROJECT_DOCKER_TAG := steemit/$(PROJECT_NAME)
PROJECT_DOCKER_RUN_ARGS := -p8080:8080

PIPENV_VENV_IN_PROJECT := 1
export PIPENV_VENV_IN_PROJECT

ENVFILE := .env

.DEFAULT_GOAL := help


.PHONY: help
help:
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: init
init:
	pip3 install pipenv
	pipenv install --three --dev
	pipenv run pre-commit install

.PHONY: clean
clean:
	find . -name "__pycache__" | xargs rm -rf
	-rm -rf .cache
	-rm -rf .eggs
	-rm -rf .mypy_cache
	-rm -rf *.egg-info
	-rm -rf *.log
	-rm -rf service/*/supervise

.PHONY: build
build: clean clean-perf
	docker build -t $(PROJECT_DOCKER_TAG) .

.PHONY: run
run:
	docker run $(PROJECT_DOCKER_RUN_ARGS) $(PROJECT_DOCKER_TAG)

.PHONY: run-local
run-local: ## run the python app without docker
	pipenv run python3 -m jussi.serve  --server_workers=1

.PHONY: test
test: ## run all tests
	pipenv run pytest

.PHONY: test-with-docker
test-with-docker: ## run tests that depend on docker
	pipenv run pytest -m'docker'

.PHONY: lint
lint: ## lint python files
	pipenv run pylint $(PROJECT_NAME)

.PHONY: fmt
fmt: ## format python files
    # yapf is disabled until the update 3.6 fstring compat
	#pipenv run yapf --in-place --style pep8 --recursive $(PROJECT_NAME)
	pipenv run autopep8 --aggressive --in-place  --jobs 0 --recursive $(PROJECT_NAME)

.PHONY: fix-imports
fix-imports: ## remove unused imports from python files
	pipenv run autoflake --in-place --remove-all-unused-imports --recursive $(PROJECT_NAME)

.PHONY: pre-commit
pre-commit: ## run pre-commit against modified files
	pipenv run pre-commit run

.PHONY: pre-commit-all
pre-commit-all: ## run pre-commit against all files
	pipenv run pre-commit run --all-files

.PHONY: check-all
check-all: pre-commit-all test

.PHONY: prepare
prepare: test build fmt fix-imports lint pre-commit-all

.PHONY: mypy
mypy: ## run mypy type checking on python files
	pipenv run mypy --ignore-missing-imports $(PROJECT_NAME)

.PHONY: curl-check
curl-check:
	curl http://localhost:8080/
	curl http://localhost:8080/health
	curl http://localhost:8080/.well-known/healthcheck.json
	curl -d '{"id":1,"jsonrpc":"2.0","method":"get_block","params":[1000]}' \
	-H'Content-Type:application/json' \
	localhost:8080

.PHONY: steemd-calls
steemd-calls:
	pipenv run python tests/make_api_calls.py tests/steemd_jsonrpc_calls.json http://localhost:8080

./perf:
	mkdir $@

%.pstats: perf
	pipenv run python -m cProfile -o $*.pstats tests/perf/$(notdir $*).py

%.png: %.pstats
	pipenv run gprof2dot -f pstats $< | dot -Tpng -o $@

.PHONY: clean-perf
clean-perf:
	rm -rf $(ROOT_DIR)/perf

.PHONY: install-python-steem-macos
install-python-steem-macos:
	env LDFLAGS="-L$(brew --prefix openssl)/lib" CFLAGS="-I$(brew --prefix openssl)/include" pipenv install steem
