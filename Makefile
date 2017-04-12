SHELL := /bin/bash
ROOT_DIR := $(shell pwd)

PROJECT_NAME := jussi
PROJECT_DOCKER_TAG := steemit/$(PROJECT_NAME)
PROJECT_DOCKER_RUN_ARGS := -p8080:8080

default: build

.PHONY: test run test-without-lint test-pylint fmt test-without-build build

init:
	pip install pipenv
	pipenv lock
	pipenv install --three --dev

build:
	docker build -t $(PROJECT_DOCKER_TAG) .

run:
	docker run $(PROJECT_DOCKER_RUN_ARGS) $(PROJECT_DOCKER_TAG)

test:
	pipenv run py.test tests


lint:
	pipenv run py.test --pylint -m pylint jussi

fmt:
	pipenv run yapf --recursive --in-place --style pep8 jussi
	pipenv run autopep8 --recursive --in-place jussi

