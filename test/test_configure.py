from copy import deepcopy
from mock import Mock
from unittest import TestCase

from dsconfig.configure import update_server
from dsconfig.utils import ObjectWrapper, find_device
from dsconfig.appending_dict import AppendingDict


TEST_DATA = {
    "servers": {
        "TangoTest/test": {
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
    },
    "classes": {
        "TangoTest": {
            "attribute_properties": {
                "boolean_scalar":  {
                    "flipperspel": ["fiskotek"]
                }
            }
        }
    }
}


class ConfigureTestCase(TestCase):

    def setUp(self):
        self.db = ObjectWrapper(None)

    def test_update_server_no_changes(self):
        update_server(self.db, Mock, "test", TEST_DATA["servers"]["TangoTest/test"],
                      TEST_DATA["servers"]["TangoTest/test"])

        self.assertListEqual(self.db.calls, [])

    def test_update_server_add_device(self):

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

        new_data = deepcopy(TEST_DATA)
        dev = find_device(new_data, "sys/tg_test/2")[0]
        dev["properties"]["flepp"] = ["56"]

        update_server(self.db, Mock, "test", new_data["servers"]["TangoTest/test"],
                      TEST_DATA["servers"]["TangoTest/test"])

        self.assertListEqual(
            self.db.calls,
            [('put_device_property', ('sys/tg_test/2', {'flepp': ['56']}), {})])

    def test_update_server_remove_property(self):

        new_data = deepcopy(TEST_DATA)
        dev = find_device(new_data, "sys/tg_test/2")[0]
        del dev["properties"]["bepa"]

        update_server(self.db, Mock, "test", new_data["servers"]["TangoTest/test"],
                      TEST_DATA["servers"]["TangoTest/test"])

        self.assertEqual(len(self.db.calls), 1)
        dbcall, args, kwargs = self.db.calls[0]
        self.assertEqual(dbcall, "delete_device_property")
        self.assertEqual(args[0], "sys/tg_test/2")
        self.assertTrue(len(args[1]) == 1)
        self.assertTrue("bepa" in args[1])  # can be list or dict
