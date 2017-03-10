SHELL := /bin/bash
ROOT_DIR := $(shell pwd)
PROJECT_NAME := jussi

default: build

.PHONY: test run test-without-lint test-pylint fmt test-without-build build

build:
	docker build -t steemit/$(PROJECT_NAME) .

run:
	docker run steemit/$(PROJECT_NAME)

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