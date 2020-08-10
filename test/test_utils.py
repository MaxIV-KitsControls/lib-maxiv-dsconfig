import pytest
import unittest
from mock import Mock

from dsconfig.tangodb import is_protected
from dsconfig.utils import progressbar, CaselessDict, ImmutableDict
from dsconfig.diff import print_diff


@pytest.fixture
def db():
    return Mock()


def test_is_protected():
    assert is_protected("__SubDevices")
    assert is_protected("polled_attr")


def test_get_dict_from_db_skips_protected(db, monkeypatch):
    DATA = {
        "servers": {
            "TangoTest/test": {
                "TangoTest": {
                    "sys/tg_test/1": {
                        "properties": {
                            "SomeProperty": ["a"]
                        }}}}}}


def test_progressbar_when_only_one_item():
    progressbar(0, 1, 100)
    progressbar(0, 1, 100)


def test_caseless_dict():
    test_dict = CaselessDict({})
    test_dict['Key1'] = 'Value1'
    assert 'KEY1' in test_dict
    test_dict['keY1'] = 'Value1a'
    assert test_dict['Key1'] != 'Value1'
    assert 'Value1a' == test_dict.pop('key1')

    test_dict['Key2'] = 'Value2'
    del(test_dict['kEy2'])

    test_dict['Key3'] = 'Value3'
    test_dict.changekey('keY3')
    assert 'key3' in test_dict
    assert 'KEY3' in test_dict


class TestImmutableDict(unittest.TestCase):
    def test_immutable(self):
        test_dict = ImmutableDict({'key1': 'value1'})
        with self.assertRaises(TypeError):
            test_dict['key2'] = 'value2'


def test_print_diff(capsys):
    test_str = ('[{"op": "remove", "path": "/a"}, {"op": "add", "path": "/c", "value": 4}'
                ', {"op": "replace", "path": "/b", "value": 3}]')
    print(test_str)
    print(str(print_diff({'a': 1, 'b': 2}, {'b': 3, 'c': 4})))
    assert test_str == str(print_diff({'a': 1, 'b': 2}, {'b': 3, 'c': 4}))
    captured = capsys.readouterr()
    assert "REMOVE:\n > a" in captured.out
    assert "ADD:\n > c" in captured.out
    assert "REPLACE:\n > b" in captured.out
