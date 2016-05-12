"""
Takes a list of server/class/devices (optionally with wildcards)
and returns the current configuration for those in JSON dsconfig format.

Note that using device or class will only return devices that are
currently exported. Perhaps there is a way to do it without?
"""

from itertools import izip, islice
import json

from tangodb import (get_devices_for_class,
                     get_devices_by_name_and_class,
                     get_device_property_values,
                     get_device_attribute_property_values)
from appending_dict import AppendingDict
import PyTango


def pairwise(t):
    it = iter(t)
    return izip(it, it)


def nwise(t, n):
    # (s_0, s_1, ...) -> ((s_0, s_1, ... , s_n-1), (s_n, ..., s_2n-1), ...)
    # Note: b0rken!
    it = iter(t)
    return izip(*islice(it, n))


def get_db_data(db, patterns=None, include_dserver=False):
    # dump TANGO database into JSON. Optionally filter which things to include
    # (currently only "positive" filters are possible; you can say which
    # servers/classes/devices to include, but you can't exclude selectively)
    # By default, dserver devices aren't included!

    data = AppendingDict()
    all_devices = {}
    dbproxy = PyTango.DeviceProxy(db.dev_name())

    if not patterns:
        # the user did not specify a pattern, so we will dump *everything*
        servers = db.get_server_list("*")
        for server in servers:
            srv, inst = server.split("/")
            devs_clss = db.get_device_class_list(server)
            for dev, clss in pairwise(devs_clss):
                if clss != "DServer" or include_dserver:
                    all_devices[dev] = data.servers[srv][inst][clss][dev]
    else:
        # go through all patterns and fill the data
        for pattern in patterns:
            prefix, pattern = pattern.split(":")
            if prefix == "server":
                servers = db.get_server_list(pattern)
                for server in servers:
                    srv, inst = server.split("/")
                    devs_clss = db.get_device_class_list(server)
                    for dev, clss in pairwise(devs_clss):
                        if clss != "DServer" or include_dserver:
                            all_devices[dev] = data.servers[srv][inst][clss][dev]
            elif prefix == "class":
                classes = db.get_class_list(pattern)
                for clss in classes:
                    devs = get_devices_for_class(dbproxy, clss)
                    for dev in devs:
                        info = db.get_device_info(dev)
                        server = info.ds_full_name
                        srv, inst = server.split("/")
                        if clss != "DServer" or include_dserver:
                            all_devices[dev] = data.servers[srv][inst][clss][dev]
            elif prefix == "device":
                devs = get_devices_by_name_and_class(dbproxy, pattern)
                for dev in devs:
                    info = db.get_device_info(dev)
                    server = info.ds_full_name
                    clss = info.class_name
                    srv, inst = server.split("/")
                    if clss != "DServer" or include_dserver:
                        all_devices[dev] = data.servers[srv][inst][clss][dev]

    # go through all found devices and get properties
    for device, devdata in all_devices.items():
        # device properties
        props = get_device_property_values(dbproxy, device, "*")
        if props:
            devdata["properties"] = props
        # attribute properties (e.g. configuration, memorized values...)
        attr_props = get_device_attribute_property_values(dbproxy, device)
        if attr_props:
            devdata["attribute_properties"] = attr_props

    return data.to_dict()


def main():
    from optparse import OptionParser
    import sys

    usage = "Usage: %prog [term:pattern term2:pattern2...]"
    parser = OptionParser(usage=usage)

    _, args = parser.parse_args()

    db = PyTango.Database()
    dbdata = get_db_data(db, args)
    print json.dumps(dbdata, indent=4)


if __name__ == "__main__":
    main()
