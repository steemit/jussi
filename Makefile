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

.PHONY: init build run run-local test lint fmt pre-commit pre-commit-all build-then-run check-all steemd-calls

init:
	pip3 install pipenv
	pipenv install --three --dev
	pipenv run python3 setup.py develop
	pipenv pre-commit install

docker-image: requirements.txt
	docker build -t $(PROJECT_DOCKER_TAG) .

Pipfile.lock: Pipfile
	python3.6 -m pipenv --python 3.6 lock --three --hashes

requirements.txt: Pipfile.lock
	python3.6 -m pipenv lock -r >requirements.txt


build: docker-image
	docker build -t $(PROJECT_DOCKER_TAG) .

run:
	docker run $(PROJECT_DOCKER_RUN_ARGS) $(PROJECT_DOCKER_TAG)

build-then-run: build
	docker run $(PROJECT_DOCKER_RUN_ARGS) $(PROJECT_DOCKER_TAG)

run-local:
	env LOG_LEVEL=DEBUG pipenv run python3 jussi/serve.py  --server_workers=1

test:
	pipenv run pytest

build-without-docker:
	python3.6 -m pipenv install --python 3.6 --three --dev
	python3.6 -m pipenv run python3.6 scripts/doc_rst_convert.py
	python3.6 -m pipenv run python3.6 setup.py build


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

curl-check: run
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
