"""
Takes a list of server/class/devices (optionally with wildcards)
and returns the current configuration for those in JSON dsconfig format.

Note that using device or class will only return devices that are
currently exported. Perhaps there is a way to do it without?
"""

from itertools import izip
import json

from utils import get_dict_from_db
from appending_dict import AppendingDict
import PyTango


def pairwise(t):
    it = iter(t)
    return izip(it, it)


def get_empty_data(db, patterns=None):
    data = AppendingDict()
    if not patterns:
        servers = db.get_server_list("*")
        for server in servers:
            devs_clss = db.get_device_class_list(server)
            for dev, clss in pairwise(devs_clss):
                if clss != "DServer":
                    data.servers[server][clss][dev] = {}
        return data
    for pattern in patterns:
        prefix, pattern = pattern.split(":")
        if prefix == "server":
            servers = db.get_server_list(pattern)
            for server in servers:
                devs_clss = db.get_device_class_list(server)
                for dev, clss in pairwise(devs_clss):
                    if clss != "DServer":
                        data.servers[server][clss][dev] = {}
        elif prefix == "class":
            classes = db.get_class_list(pattern)
            for clss in classes:
                devs = db.get_device_exported_for_class(clss)
                for dev in devs:
                    info = db.get_device_info(dev)
                    server = info.ds_full_name
                    print server
                    data.servers[server][clss][dev] = {}
        elif prefix == "device":
            devices = db.get_device_exported(pattern)
            for device in devices:
                info = db.get_device_info(device)
                server = info.ds_full_name
                clss = info.class_name
                data.servers[server][clss][device] = {}

    return data.to_dict()


def get_db_data(db, empty_data):
    return get_dict_from_db(db, empty_data, narrow=True)[0]


def main():
    from optparse import OptionParser
    import sys

    usage = "Usage: %prog [term:pattern term2:pattern2...]"
    parser = OptionParser(usage=usage)

    _, args = parser.parse_args()

    db = PyTango.Database()
    data = get_empty_data(db, args)
    if not data:
        sys.exit("No matches in the Tango DB; are the devices exported?")
    dbdata = get_db_data(db, data)
    print json.dumps(dbdata, indent=4)


if __name__ == "__main__":
    main()
