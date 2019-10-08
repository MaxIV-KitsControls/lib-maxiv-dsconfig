#!/usr/bin/env python

from setuptools import setup

setup(
    # Package
    name="python-dsconfig",
    version="1.3.1",
    packages=['dsconfig', 'dsconfig.appending_dict'],
    description="Library and utilities for Tango device configuration.",
    # Requirements
    setup_requires=['setuptools', 'pytest-runner'],
    install_requires=['jsonpatch>=1.13', 'jsonschema', 'xlrd', 'PyTango'],
    tests_require=["pytest", "pytest-cov", "Faker", "mock"],
    # Resources
    package_data={
        'dsconfig': ['schema/dsconfig.json',
                     'schema/schema2.json']},
)
