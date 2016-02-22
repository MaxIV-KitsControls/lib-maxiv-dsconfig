#!/usr/bin/env python

from setuptools import setup

setup(
    name="python-dsconfig",
    version="1.0.0",
    install_requires=['jsonpatch>=1.13'],
    description="Library and utilities for Tango device configuration.",
    packages=['dsconfig', 'dsconfig.appending_dict'],
    test_suite="nose.collector",
    package_data={'dsconfig': ['schema/dsconfig.json', 'schema/schema2.json']},
    entry_points={
        'console_scripts': ['xls2json = dsconfig.excel:main',
                            'csv2json = dsconfig.callcsv:main',
                            'json2tango = dsconfig.json2tango.main']}
)
