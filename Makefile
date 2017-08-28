SHELL := /bin/bash
ROOT_DIR := $(shell pwd)

PROJECT_NAME := $(notdir $(ROOT_DIR))
PROJECT_DOCKER_TAG := steemit/$(PROJECT_NAME)
PROJECT_DOCKER_RUN_ARGS := -p8080:8080

PIPENV_VENV_IN_PROJECT := 1
export PIPENV_VENV_IN_PROJECT

ENVFILE := .env
ENVDIR := envd
ENVVARS = $(wildcard $(ENVDIR)/* )

default: build

.PHONY: init clean build run run-local test lint fmt pre-commit pre-commit-all build-then-run check-all steemd-calls

init:
	pip3 install pipenv
	pipenv install --three --dev
	pipenv run pre-commit install

clean:
	find . -name "__pycache__" | xargs rm -rf
	-rm -rf .cache
	-rm -rf .eggs
	-rm -rf .mypy_cache
	-rm -rf *.egg-info
	-rm -rf *.log

build: clean clean-perf
	docker build -t $(PROJECT_DOCKER_TAG) .

run:
	docker run $(PROJECT_DOCKER_RUN_ARGS) $(PROJECT_DOCKER_TAG)

build-then-run: build
	docker run $(PROJECT_DOCKER_RUN_ARGS) $(PROJECT_DOCKER_TAG)

run-local:
	env LOG_LEVEL=DEBUG pipenv run python3 -m jussi.serve  --server_workers=1

test:
	pipenv run pytest

test-without-docker:
	pipenv run pytest --fulltrace -m'not docker'

lint:
	pipenv pre-commit run pylint --all-files

fmt:
	pipenv run yapf --in-place --style pep8 --parallel --recursive $(PROJECT_NAME)
	pipenv run autopep8 --aggressive --in-place  --jobs 0 --recursive $(PROJECT_NAME)
	pipenv run autoflake --remove-all-unused-imports --recursive $(PROJECT_NAME)

pre-commit:
	pipenv run pre-commit run

pre-commit-all:
	pipenv run pre-commit run --all-files

check-all: pre-commit-all test

mypy:
	pipenv run mypy --ignore-missing-imports $(PROJECT_NAME)

$(ENVFILE): $(ENVDIR)
	for f in $(notdir $(ENVVARS)) ; do \
    	echo $$f=`cat $(ENVDIR)/$$f` >> $@ ; \
    done; \

$(ENVDIR):
	-mkdir $@

curl-check:
	curl http://localhost:8080/
	curl http://localhost:8080/health
	curl http://localhost:8080/.well-known/healthcheck.json
	curl -d '{"id":1,"jsonrpc":"2.0","method":"get_block","params":[1000]}' \
	-H'Content-Type:application/json' \
	localhost:8080

steemd-calls:
	pipenv run python tests/make_api_calls.py tests/steemd_jsonrpc_calls.json http://localhost:8080

./perf:
	mkdir $@

%.pstats: perf
	pipenv run python -m cProfile -o $*.pstats tests/perf/$(notdir $*).py

%.png: %.pstats
	pipenv run gprof2dot -f pstats $< | dot -Tpng -o $@

clean-perf:
	rm -rf $(ROOT_DIR)/perf
