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
	pipenv run yapf --in-place --style pep8 --parallel --recursive $(PROJECT_NAME)
	pipenv run autopep8 --aggressive --in-place  --jobs 0 --recursive $(PROJECT_NAME)
	pipenv run autoflake --remove-all-unused-imports --recursive $(PROJECT_NAME)

pre-commit:
	pipenv run pre-commit run

pre-commit-all:
	pipenv run pre-commit run --all-files

mypy:
	pipenv run mypy --ignore-missing-imports $(PROJECT_NAME)

curl-check:
	-curl http://localhost:8080/
	curl http://localhost:8080/health
	curl http://localhost:8080/.well-known/healthcheck.json
	curl -d '{"id":1,"jsonrpc":"2.0","method":"get_block","params":[1000]}' \
	-H'Content-Type:application/json' \
	localhost:8080
