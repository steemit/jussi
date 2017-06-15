#!/usr/bin/env python
import os
from setuptools import setup
try:
    from pipenv.project import Project
    from pipenv.utils import convert_deps_to_pip
except ImportError:
    raise Exception('setup requires pipenv. Run "pip3 install pipenv" then try again')

pfile = Project().parsed_pipfile
requirements = convert_deps_to_pip(pfile['packages'], r=False)
test_requirements = convert_deps_to_pip(pfile['dev-packages'], r=False)

base_dir = os.path.dirname(__file__)

about = {}

with open(os.path.join(base_dir, "jussi", "__about__.py")) as f:
    exec(f.read(), about)

with open(os.path.join(base_dir, "README.md")) as f:
    long_description = f.read()


setup(
    name=about["__title__"],
    version=about["__version__"],

    description=about["__summary__"],
    long_description=long_description,
    url=about["__uri__"],

    author=about["__author__"],
    author_email=about["__email__"],

    setup_requires=['pipenv','pytest-runner'],
    tests_require=test_requirements,
    install_requires=requirements,

    packages=["jussi"],
    entry_points={
        'console_scripts': ['jussi=jussi.serve:main']
    }
)