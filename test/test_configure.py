from copy import deepcopy
from mock import Mock
try:
    from unittest2 import TestCase
except ImportError:
    from unittest import TestCase

from dsconfig.configure import (update_server, update_device_or_class,
                                update_properties)
from dsconfig.formatting import CLASSES_LEVELS, SERVERS_LEVELS
from dsconfig.utils import ObjectWrapper, find_device
from dsconfig.appending_dict import AppendingDict


TEST_DATA = {
    "servers": {
        "TangoTest": {
            "test": {
                "TangoTest": {
                    "sys/tg_test/2": {
                        "properties": {
                            "bepa": ["45"]
                        },
                        "attribute_properties": {
                            "ampliz": {
                                "min_value": ["100"],
                                "unit": ["hejsan"]
                            }
                        }
                    }
                }
            }
        }
    },
    "classes": {
        "TangoTest": {
            "attribute_properties": {
                "boolean_scalar": {
                    "flipperspel": ["fiskotek"]
                }
            }
        }
    },
    "devices": {
        "a/b/c": {
            "properties": {
                "foo": ["bar"]
            }
        }
    }
}


class ConfigureTestCase(TestCase):

    def setUp(self):
        self.db = ObjectWrapper(None)
        self.dbdict = deepcopy(TEST_DATA)
        self.data = deepcopy(TEST_DATA)

    def test_update_server_no_changes(self):
        update_server(self.db, Mock, "test",
                      self.dbdict["servers"]["TangoTest"]["test"],
                      self.dbdict["servers"]["TangoTest"]["test"])

        self.assertListEqual(self.db.calls, [])

    def test_update_server_add_device_2(self):

        new_data = {
            "TangoTest": {
                "sys/tg_test/apa": {}
            }
        }

        update_server(self.db, Mock, "TangoTest/1", new_data, AppendingDict())

        self.assertEqual(len(self.db.calls), 1)
        dbcall, args, kwargs = self.db.calls[0]
        self.assertEqual(dbcall, 'add_device')
        self.assertEqual(args[0].name, 'sys/tg_test/apa')
        self.assertEqual(args[0]._class, "TangoTest")
        self.assertEqual(args[0].server, "TangoTest/1")

    def test_update_server_add_property(self):

        dev = find_device(self.data, "sys/tg_test/2")[0]
        dev["properties"]["flepp"] = ["56"]

        update_server(self.db, Mock, "test", self.data["servers"]["TangoTest"]["test"],
                      self.dbdict["servers"]["TangoTest"]["test"])

        self.assertListEqual(
            self.db.calls,
            [('put_device_property', ('sys/tg_test/2', {'flepp': ['56']}), {})])

    def test_update_server_remove_property(self):

        dev = find_device(self.data, "sys/tg_test/2")[0]
        del dev["properties"]["bepa"]

        update_server(self.db, Mock, "test",
                      self.data["servers"]["TangoTest"]["test"],
                      self.dbdict["servers"]["TangoTest"]["test"])

        self.assertEqual(len(self.db.calls), 1)
        dbcall, args, kwargs = self.db.calls[0]
        self.assertEqual(dbcall, "delete_device_property")
        self.assertEqual(args[0], "sys/tg_test/2")
        self.assertTrue(len(args[1]) == 1)
        self.assertTrue("bepa" in args[1])  # can be list or dict

    def test_update_server_remove_device(self):
        devname = "sys/tg_test/2"
        del self.data["servers"]["TangoTest"]["test"]["TangoTest"][devname]
        update_server(self.db, Mock, "test",
                      self.data["servers"]["TangoTest"]["test"],
                      self.dbdict["servers"]["TangoTest"]["test"])
        self.assertEqual(len(self.db.calls), 1)
        dbcall, args, kwargs = self.db.calls[0]
        self.assertEqual(dbcall, "delete_device")
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0], devname)

    def test_update_server_remove_device_update_skips(self):
        devname = "sys/tg_test/2"
        del self.data["servers"]["TangoTest"]["test"]["TangoTest"][devname]
        update_server(self.db, Mock, "test",
                      self.data["servers"]["TangoTest"]["test"],
                      self.dbdict["servers"]["TangoTest"]["test"],
                      update=True)
        self.assertEqual(len(self.db.calls), 0)

    def test_update_server_add_empty_device(self):
        new_devname = "a/new/dev"
        dev = {}
        self.data["servers"]["TangoTest"]["test"]["TangoTest"][new_devname] = dev
        update_server(self.db, Mock, "TangoTest/test",
                      self.data["servers"]["TangoTest"]["test"],
                      self.dbdict["servers"]["TangoTest"]["test"])
        # verify the db calls made
        self.assertEqual(len(self.db.calls), 1)
        dbcall, args, kwargs = self.db.calls[0]
        self.assertEqual(dbcall, "add_device")
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0].server, "TangoTest/test")
        self.assertEqual(args[0].name, new_devname)

    def test_update_server_add_device_with_property(self):
        new_devname = "a/new/dev"
        dev = {"properties": {"test": ["hello"]}}
        self.data["servers"]["TangoTest"]["test"]["TangoTest"][new_devname] = dev
        update_server(self.db, Mock, "TangoTest/test",
                      self.data["servers"]["TangoTest"]["test"],
                      self.dbdict["servers"]["TangoTest"]["test"])
        self.assertEqual(len(self.db.calls), 2)
        dbcall, args, kwargs = self.db.calls[0]
        self.assertEqual(dbcall, "add_device")
        self.assertEqual(len(args), 1)
        self.assertEqual(args[0].name, new_devname)
        dbcall, args, kwargs = self.db.calls[1]
        self.assertEqual(dbcall, "put_device_property")
        self.assertEqual(len(args), 2)
        self.assertEqual(args[0], new_devname)
        self.assertDictEqual(args[1], {"test": ["hello"]})

    # === tests for update_class ===

    def test_update_device_or_class_add_property(self):
        new_classname = "SomeClass"
        cls = {"properties": {"test": ["hello"]}}
        update_device_or_class(self.db, new_classname, {}, cls, cls=True)
        self.assertEqual(len(self.db.calls), 1)
        dbcall, args, kwargs = self.db.calls[0]
        self.assertEqual(dbcall, "put_class_property")
        self.assertEqual(len(args), 2)
        self.assertEqual(args[0], new_classname)
        self.assertDictEqual(args[1], {"test": ["hello"]})

    # === tests for update_properties ===

    def test_update_properties_add_property(self):
        devname = "sys/tg_test/2"
        dev = find_device(self.data, devname)[0]
        dev["properties"]["flepp"] = ["56"]
        orig_dev = find_device(self.dbdict, devname)[0]
        added, removed = update_properties(self.db, devname,
                                           orig_dev["properties"],
                                           dev["properties"])
        self.assertDictEqual(added, {"flepp": ["56"]})
        self.assertDictEqual(removed, {})
        self.assertListEqual(
            self.db.calls,
            [('put_device_property', ('sys/tg_test/2', {'flepp': ['56']}), {})])

    def test_update_properties_remove_property(self):
        devname = "sys/tg_test/2"
        dev = find_device(self.data, devname)[0]
        del dev["properties"]["bepa"]
        orig_dev = find_device(self.dbdict, devname)[0]
        added, removed = update_properties(self.db, devname,
                                           orig_dev["properties"],
                                           dev["properties"])
        self.assertDictEqual(added, {})
        self.assertIn("bepa", removed)
        self.assertListEqual(
            self.db.calls,
            [('delete_device_property', ('sys/tg_test/2', {'bepa': ['45']}), {})])

    def test_update_properties_remove_property_leaves_protected(self):
        devname = "sys/tg_test/2"
        dev = find_device(self.dbdict, devname)[0]
        dev["properties"]["polled_attr"] = ["a", "b"]
        orig_dev = find_device(self.dbdict, devname)[0]
        added, removed = update_properties(self.db, devname,
                                           orig_dev["properties"],
                                           dev["properties"])
        self.assertDictEqual(added, {})
        self.assertDictEqual(removed, {})

    def test_update_properties_replace_property(self):
        devname = "sys/tg_test/2"
        dev = find_device(self.data, devname)[0]
        dev["properties"]["bepa"] = ["573"]
        orig_dev = find_device(self.dbdict, devname)[0]
        added, removed = update_properties(self.db, devname,
                                           orig_dev["properties"],
                                           dev["properties"])
        self.assertIn("bepa", added)
        self.assertListEqual(
            self.db.calls,
            [('put_device_property', ('sys/tg_test/2', {'bepa': ['573']}), {})])


    def test_update_properties_add_attribute_property(self):
        devname = "sys/tg_test/2"
        label = "This is a test"
        dev = find_device(self.data, devname)[0]
        dev["attribute_properties"]["someAttr"] = {"label": [label]}
        orig_dev = find_device(self.dbdict, devname)[0]
        added, removed = update_properties(self.db, devname,
                                           orig_dev["attribute_properties"],
                                           dev["attribute_properties"],
                                           attr=True)
        self.assertDictEqual(added, {"someAttr": {"label": [label]}})
        self.assertDictEqual(removed, {})
        self.assertEqual(len(self.db.calls), 1)
        self.assertListEqual(
            self.db.calls,
            [('put_device_attribute_property',
              ('sys/tg_test/2', {'someAttr': {'label': [label]}}), {})])

    # def test_update_properties_remove_property(self):
    #     devname = "sys/tg_test/2"
    #     dev = find_device(self.data, devname)[0]
    #     del dev["properties"]["bepa"]
    #     orig_dev = find_device(self.dbdict, devname)[0]
    #     added, removed = update_properties(self.db, devname,
    #                                        orig_dev["properties"],
    #                                        dev["properties"])
    #     self.assertDictEqual(added, {})
    #     self.assertIn("bepa", removed)
    #     self.assertListEqual(
    #         self.db.calls,
    #         [('delete_device_property', ('sys/tg_test/2', {'bepa': ['45']}), {})])

    # def test_update_properties_replace_property(self):
    #     devname = "sys/tg_test/2"
    #     dev = find_device(self.data, devname)[0]
    #     dev["properties"]["bepa"] = ["573"]
    #     orig_dev = find_device(self.dbdict, devname)[0]
    #     added, removed = update_properties(self.db, devname,
    #                                        orig_dev["properties"],
    #                                        dev["properties"])
    #     self.assertIn("bepa", added)
    #     self.assertListEqual(
    #         self.db.calls,
    #         [('put_device_property', ('sys/tg_test/2', {'bepa': ['573']}), {})])
