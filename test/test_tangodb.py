import PyTango
import pytest
from dsconfig.tangodb import get_dict_from_db
from dsconfig.utils import ObjectWrapper, find_device
from unittest.mock import Mock, MagicMock, create_autospec


def make_db(dbdata):
    db = create_autospec(PyTango.Database)

    def get_device_info(dev):
        _, (srv, inst, clss, _) = find_device(dbdata, dev)
        return MagicMock(ds_full_name="%s/%s" % (srv, inst), name=dev,
                         class_name=clss)
    db.get_device_info.side_effect = get_device_info

    def get_device_name(server, clss):
        srv, inst = server.split("/")
        return list(dbdata["servers"][srv][inst][clss].keys())
    db.get_device_name.side_effect = get_device_name

    def get_device_property_list(dev, pattern):
        data, _ = find_device(dbdata, dev)
        return list(data["properties"].keys())
    db.get_device_property_list.side_effect = get_device_property_list

    def get_device_property(dev, props):
        data, _ = find_device(dbdata, dev)
        return dict((p, data["properties"][p]) for p in props)
    db.get_device_property.side_effect = get_device_property

    return db


def test_get_dict_from_db():

    indata = {
        "servers": {
            "testserver": {
                "testinstance": {
                    "testclass": {
                        "a/b/c": {}
                    }}}}}

    dbdata = {
        "servers": {
            "testserver": {
                "testinstance": {
                    "testclass": {
                        "a/b/c": {
                            "properties": {
                                "a": ["78", "103"]
                            }}}}}}}

    db = make_db(dbdata)
    print(get_dict_from_db(db, indata))
