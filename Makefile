SHELL := /bin/bash
ROOT_DIR := $(shell pwd)

PROJECT_NAME := jussi
PROJECT_DOCKER_TAG := steemit/$(PROJECT_NAME)
PROJECT_DOCKER_RUN_ARGS := -p8080:8080

default: build

.PHONY: init build run run-local test lint fmt

init:
	pip3 install pipenv
	pipenv lock
	pipenv install --three --dev

build:
	docker build -t $(PROJECT_DOCKER_TAG) .

run: build
	docker run $(PROJECT_DOCKER_RUN_ARGS) $(PROJECT_DOCKER_TAG)

run-local:
	pipenv run python3 jussi/serve.py

test:
	pipenv run py.test tests


lint:
	pipenv run py.test --pylint -m pylint jussi

fmt:
	pipenv run yapf --recursive --in-place --style pep8 jussi
	pipenv run autopep8 --recursive --in-place jussi