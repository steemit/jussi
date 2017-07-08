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

build:
	docker build -t $(PROJECT_DOCKER_TAG) .

run:
	docker run $(PROJECT_DOCKER_RUN_ARGS) $(PROJECT_DOCKER_TAG)

run-local:
	pipenv run python3 jussi/serve.py

test:
	pipenv run py.test tests

lint:
	pipenv run py.test --pylint -m pylint $(PROJECT_NAME)

fmt:
	pipenv run yapf --recursive --in-place --style pep8 $(PROJECT_NAME)
	pipenv run autopep8 --recursive --in-placedo $(PROJECT_NAME)