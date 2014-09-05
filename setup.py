#!/usr/bin/env python

from setuptools import setup

setup(name = "python-dsconfig",
      version = "0.1.0",
      description = "Library and utilities for Tango device configuration.",
      packages = ['dsconfig', 'dsconfig.appending_dict'],
      test_suite = "nose.collector",
      package_data = {'dsconfig': ['schema/dsconfig.json']},
      scripts = ["bin/xls2json", "bin/json2tango"]
)
rements
