import json

from unittest.mock import MagicMock, patch
from os.path import dirname, abspath, join

from .test_tangodb import make_db
from dsconfig.dump import get_db_data


query1 = ("SELECT device, property_device.name, property_device.value FROM "
          "property_device INNER JOIN device ON property_device.device = device.name "
          "WHERE server LIKE '%' AND class LIKE '%' AND device LIKE '%' AND "
          "class != 'DServer' AND property_device.name != '__SubDevices'")
query2 = ("SELECT device, attribute, property_attribute_device.name, "
          "property_attribute_device.value FROM property_attribute_device INNER JOIN "
          "device ON property_attribute_device.device = device.name WHERE server "
          "LIKE '%' AND class LIKE '%' AND device LIKE '%' AND class != 'DServer'")
query3 = ("SELECT server, class, name, alias FROM device WHERE server LIKE '%' AND "
          "class LIKE '%' AND name LIKE '%' AND class != 'DServer'")
query4 = ("select DISTINCT property_class.class, property_class.name, "
          "property_class.value FROM property_class INNER JOIN device ON "
          "property_class.class = device.class WHERE server like '%' AND "
          "device.class != 'DServer' AND device.class != 'TangoAccessControl'")
query5 = ("select DISTINCT  property_attribute_class.class, "
          "property_attribute_class.attribute, property_attribute_class.name, "
          "property_attribute_class.value FROM property_attribute_class INNER JOIN "
          "device ON property_attribute_class.class = device.class WHERE server "
          "like '%' AND device.class != 'DServer' AND "
          "device.class != 'TangoAccessControl'")
query6 = ("select DISTINCT  property_attribute_class.class, "
          "property_attribute_class.attribute, property_attribute_class.name, "
          "property_attribute_class.value FROM property_attribute_class INNER JOIN "
          "device ON property_attribute_class.class = device.class WHERE server "
          "like 'SOMEDEVICE' AND device.class != 'DServer' AND "
          "device.class != 'TangoAccessControl'")
query7 = ("select DISTINCT property_class.class, property_class.name, "
          "property_class.value FROM property_class INNER JOIN device ON "
          "property_class.class = device.class WHERE server like 'SOMEDEVICE' AND "
          "device.class != 'DServer' AND device.class != 'TangoAccessControl'")
query8 = ("SELECT device, attribute, property_attribute_device.name, "
          "property_attribute_device.value FROM property_attribute_device INNER JOIN "
          "device ON property_attribute_device.device = device.name WHERE server "
          "LIKE 'SOMESERVER' AND class LIKE '%' AND device LIKE '%' AND "
          "class != 'DServer'")


def test_db_dump():
    json_data_file = join(dirname(abspath(__file__)), 'files', 'sample_db.json')
    with open(json_data_file, 'r') as json_file:
        db_data = json.load(json_file)
        db = make_db(db_data)

        with patch('dsconfig.dump.tango') as mocked_pytango:

            in_out_mock = MagicMock(name='in_out_mock', return_value = ("A", "B"))
            device_proxy_mock = MagicMock(name='device_proxy_mock')
            device_proxy_mock.command_inout = in_out_mock
            mocked_pytango.DeviceProxy.return_value = device_proxy_mock

            get_db_data(db, class_properties=True)
            assert  in_out_mock.call_count == 5
            in_out_mock.assert_any_call('DbMySqlSelect', query1)
            in_out_mock.assert_any_call('DbMySqlSelect', query2)
            in_out_mock.assert_any_call('DbMySqlSelect', query3)
            in_out_mock.assert_any_call('DbMySqlSelect', query4)
            in_out_mock.assert_any_call('DbMySqlSelect', query5)

            in_out_mock.reset_mock()
            get_db_data(db, patterns=["server:SOMESERVER", 'clss:SOMECLASS',
                                      'device:SOMEDEVICE'], class_properties=True)
            assert in_out_mock.call_count == 15
            in_out_mock.assert_any_call('DbMySqlSelect', query6)
            in_out_mock.assert_any_call('DbMySqlSelect', query7)
            in_out_mock.assert_any_call('DbMySqlSelect', query8)
