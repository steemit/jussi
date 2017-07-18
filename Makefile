SHELL := /bin/bash
ROOT_DIR := $(shell pwd)

PROJECT_NAME := $(notdir $(ROOT_DIR))
PROJECT_DOCKER_TAG := steemit/$(PROJECT_NAME)
PROJECT_DOCKER_RUN_ARGS := -p8080:8080

PIPENV_VENV_IN_PROJECT := 1
export PIPENV_VENV_IN_PROJECT

default: build

.PHONY: init build run run-local test lint fmt

init:
	pip3 install pipenv
	pipenv install --three --dev
	pipenv run python3 setup.py develop
	pipenv pre-commit install

build:
	docker build -t $(PROJECT_DOCKER_TAG) .

run:
	docker run $(PROJECT_DOCKER_RUN_ARGS) $(PROJECT_DOCKER_TAG)

run-local:
	pipenv run python3 jussi/serve.py  --server_workers=1

test:
	pipenv run py.test tests

lint:
	pipenv pre-commit run pylint --all-files

fmt:
	pipenv pre-commit run yapf --all-files
	pipenv pre-commit run autopep8 --all-files


pre-commit:
	pipenv run pre-commit run --all-files

quick-test:
	curl http://localhost:8080/
	curl http://localhost:8080/health
	curl http://localhost:8080/.well-known/healthcheck.json
	curl -d '{"id": 1, "jsonrpc":"2.0", "method": "get_block", "params": [1000]}' http://localhost:8080/

quick-test-local:
	curl http://localhost:9000/
	curl http://localhost:9000/health
	curl http://localhost:9000/.well-known/healthcheck.json
	curl -d '{"id": 1, "jsonrpc":"2.0", "method": "get_block", "params": [1000]}' http://localhost:9000/
