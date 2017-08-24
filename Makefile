ROOT_DIR := .
DOCS_DIR := $(ROOT_DIR)/docs
DOCS_BUILD_DIR := $(DOCS_DIR)/_build

PROJECT_NAME := jussi
PROJECT_DOCKER_TAG := steemit/$(PROJECT_NAME)

default: install-global

.PHONY: docker-image build-without-docker test-without-lint test-pylint test-without-build install-pipenv install-global clean clean-build

docker-image: clean
	docker build -t $(PROJECT_DOCKER_TAG) .

Pipfile.lock: Pipfile
	python3.6 -m pipenv --python /usr/local/bin/python3.6 lock --three --hashes

requirements.txt: Pipfile.lock
	python3.6 -m pipenv --python /usr/local/bin/python3.6 lock -r | grep -v Using | >requirements.txt

build-without-docker: requirements.txt Pipfile.lock
	mkdir -p build/wheel
	python3.6 -m pipenv install --python /usr/local/bin/python3.6 --three --dev
	python3.6 -m pipenv run pip3.6 install -U setuptools
	python3.6 -m pipenv run python3.6 setup.py build

dockerised-test: docker-image
	docker run -ti $(PROJECT_DOCKER_TAG) make -C /buildroot/src build-without-docker install-pipenv test-without-build

test: build-without-docker test-without-build

test-without-build: test-without-lint test-pylint

test-without-lint:
	pipenv run pytest -v

test-pylint:
	pipenv run pytest -v --pylint

clean: clean-build clean-pyc
	rm -rf requirements.txt

clean-build:
	rm -fr build/ dist/ *.egg-info .eggs/ .tox/ __pycache__/ .cache/ .coverage htmlcov src

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +

install-pipenv:
	python3.6 -m pipenv run pip3.6 install -e .

install-global:
	python3.6 scripts/doc_rst_convert.py
	pip3.6 install -e .

pypi:
	python3.6 setup.py bdist_wheel --universal
	python3.6 setup.py sdist bdist_wheel upload
	rm README.rst
