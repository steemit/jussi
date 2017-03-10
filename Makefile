SHELL := /bin/bash
ROOT_DIR := $(shell pwd)

PROJECT_NAME := jussi
PROJECT_DOCKER_TAG := steemit/$(PROJECT_NAME)
PROJECT_DOCKER_RUN_ARGS := -p8080:8080 -p9191:9191

default: build

.PHONY: test run test-without-lint test-pylint fmt test-without-build build

build:
	docker build -t $(PROJECT_DOCKER_TAG) .

run:
	docker run $(PROJECT_DOCKER_RUN_ARGS) $(PROJECT_DOCKER_TAG)

test: test-without-build build

test-without-build: test-without-lint test-pylint


test-without-lint:
	py.test tests

test-pylint:
	py.test --pylint -m pylint sbds

fmt:
	yapf --recursive --in-place --style pep8 .
	autopep8 --recursive --in-place .

requirements.txt: serve.py
	pip freeze > $@