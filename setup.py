#!/usr/bin/env python

from setuptools import setup

setup(
    # Package
    name="python-dsconfig",
    version="1.0.0",
    packages=['dsconfig', 'dsconfig.appending_dict'],
    description="Library and utilities for Tango device configuration.",
    # Requirements
    install_requires=['jsonpatch>=1.13'],
    setup_requires=['pytest-runner'],
    tests_require=["pytest", "pytest-cov", "fake-factory", "mock"],
    # Resources
    package_data={
        'dsconfig': ['schema/dsconfig.json',
                     'schema/schema2.json']},
    # Scripts
    entry_points={
        'console_scripts': ['xls2json = dsconfig.excel:main',
                            'csv2json = dsconfig.callcsv:main',
                            'json2tango = dsconfig.json2tango.main']}
)
