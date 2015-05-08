import pytest
from mock import Mock

from dsconfig.tangodb import is_protected


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
