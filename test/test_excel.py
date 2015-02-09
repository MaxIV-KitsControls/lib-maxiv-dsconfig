try:
    from unittest2 import TestCase
except ImportError:
    from unittest import TestCase

from dsconfig import excel
from dsconfig.utils import CaselessDict


class TestExcel(TestCase):

    def test_get_properties_combined(self):
        row = CaselessDict({"Properties": "a=1; b=2; c=3"})
        result = excel.get_properties(row)
        self.assertDictEqual(result, {"a": ["1"], "b": ["2"], "c": ["3"]})

    def test_get_properties_separate(self):
        row = CaselessDict({"Property:a": "1", "Property:b": "2"})
        result = excel.get_properties(row)
        self.assertDictEqual(result, {"a": ["1"], "b": ["2"]})

    def test_get_properties_both(self):
        row = CaselessDict({"Properties": "c=3",
                            "Property:a": "1", "Property:b": "2"})
        result = excel.get_properties(row)
        self.assertDictEqual(result, {"a": ["1"], "b": ["2"], "c": ["3"]})

    def test_get_properties_splits_combined(self):
        row = CaselessDict({"Properties": "a=1\n2\n3"})
        result = excel.get_properties(row)
        self.assertDictEqual(result, {"a": ["1", "2", "3"]})

    def test_get_properties_splits_separate(self):
        row = CaselessDict({"Property:a": "1\n2\n3"})
        result = excel.get_properties(row)
        self.assertDictEqual(result, {"a": ["1", "2", "3"]})

    def test_get_dynamic_attribute(self):
        row = CaselessDict({"name": "TestAttribute", "formula": "a + b",
                            "type": "int", "mode": "attr"})
        result = excel.get_dynamic(row)
        self.assertDictEqual(
            result, {"DynamicAttributes": ["TestAttribute=int(a + b)"]})

    def test_get_dynamic_command(self):
        row = CaselessDict({"name": "TestCommand", "formula": "1 + 2",
                            "type": "bool", "mode": "cmd"})
        result = excel.get_dynamic(row)
        self.assertDictEqual(
            result, {"DynamicCommands": ["TestCommand=bool(1 + 2)"]})

    def test_get_dynamic_state(self):
        row = CaselessDict({"name": "WEIRD", "formula": "1 == 2",
                            "type": "bool", "mode": "state"})
        result = excel.get_dynamic(row)
        self.assertDictEqual(
            result, {"DynamicStates": ["WEIRD=bool(1 == 2)"]})

    def test_get_dynamic_status(self):
        row = CaselessDict({"name": "Status", "formula": "'Something witty here'",
                            "type": "str", "mode": "status"})
        result = excel.get_dynamic(row)
        self.assertDictEqual(
            result, {"DynamicStatus": ["str('Something witty here')"]})

    def test_dynamic_attribute_barfs_on_bad_syntax(self):
        row = CaselessDict({"name": "TestAttribute", "formula": "a ? b",
                            "type": "int", "mode": "attr"})
        self.assertRaises(SyntaxError, excel.get_dynamic, row)

    def test_dynamic_attribute_errors_if_missing_stuff(self):
        row = CaselessDict({"name": "TestAttribute", "formula": "a + b",
                            "type": "int"})
        self.assertRaises(ValueError, excel.get_dynamic, row)

    def test_get_config(self):
        row = CaselessDict({"Attribute": "myAttribute", "Label": "Something", "Min value": 45, "Not valid": "foo"})
        result = excel.get_config(row)
        self.assertDictEqual(result,
                             {"myAttribute": {"min_value": ["45"], "label": ["Something"]}})

    def test_check_device_format_lets_valid_names_pass(self):
        excel.check_device_format("i-a/test-test/device-0")

    def test_check_device_format_ignores_case(self):
        excel.check_device_format("I-A/TEST-TEST/DEVICE-0")

    def test_check_device_format_catches_bad_names(self):
        self.assertRaises(ValueError, excel.check_device_format, "not/a/device/name")

    def test_check_device_format_catches_non_device_names(self):
        self.assertRaises(ValueError, excel.check_device_format, "just a string")

    def test_check_device_format_catches_names_with_invalid_characters(self):
        self.assertRaises(ValueError, excel.check_device_format, "I/can.has/dots")

    def test_format_server_instance(self):
        row = {"server": "TestServer", "instance": 1}
        result = excel.format_server_instance(row)
        self.assertEqual(result, "TestServer/1")

    def test_format_server_instance_handles_floats(self):
        row = {"server": "TestServer", "instance": 1.0}
        result = excel.format_server_instance(row)
        self.assertEqual(result, "TestServer/1")
