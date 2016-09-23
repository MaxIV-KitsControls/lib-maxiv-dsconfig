"Various functionality for dealing with the TANGO database"

from collections import defaultdict
from itertools import izip, islice

import PyTango

from appending_dict import AppendingDict, SetterDict
from dsconfig.utils import green, red, yellow


# These are special properties that we'll ignore for now
PROTECTED_PROPERTIES = [
    "polled_attr", "logging_level", "logging_target"
]


SPECIAL_ATTRIBUTE_PROPERTIES = [
    "label", "format", "unit", "standard_unit", "display_unit",
    "min_value", "min_alarm", "min_warning",
    "max_value", "max_alarm", "max_warning",
    "delta_t", "delta_val",
    "abs_change", "rel_change",
    "event_period", "archive_abs_change", "archive_rel_change",
    "archive_period", "description", "mode",
    "__value", "__value_ts"  # memorized attribute values go here
]


def get_devices_from_dict(dbdict):
    return [(server_name, instance_name, class_name, device_name)
            for server_name, server in dbdict.items()
            for instance_name, instance in server.items()
            for class_name, clss in instance.items()
            for device_name in clss]


def get_servers_from_dict(dbdict):
    servers = set()
    for server, children in dbdict.get("servers", {}).items():
        if "/" in server:
            servers.add(server)
        else:
            for inst in children:
                servers.add(("%s/%s" % (server, inst)).lower())
    return servers


def is_protected(prop, attr=False):
    """There are certain properties that need special treatment as they
    are handled in particular ways by Tango. In general, we don't want to
    remove these if they exist, but we do allow overwriting them."""
    if attr:
        # Attribute config properties
        return prop.startswith("_") or prop in SPECIAL_ATTRIBUTE_PROPERTIES
    else:
        return prop.startswith("_") or prop in PROTECTED_PROPERTIES


def present_calls(indata, dbdata, dbcalls):

    # WIP!

    def add_device(devname, devinfo):
        msg = ("ADD DEVICE\n" +
               "{info.server_id} / {info.dev_class} / {info.name}"
               .format(info=devinfo))
        return (green, msg)

    def delete_device(devname):
        return red, "DELETE DEVICE\n {0}".format(devname)


def summarise_calls(dbcalls, dbdata):

    "A brief summary of the operations performed by a list of DB calls"

    methods = [
        "add_device",
        "delete_device",
        "put_device_property",
        "delete_device_property",
        "put_device_attribute_property",
        "delete_device_attribute_property",
        "put_class_property",
        "delete_class_property",
        "put_class_attribute_property",
        "delete_class_attribute_property",
        "put_device_alias",
        "delete_device_alias"
    ]

    old_servers = get_servers_from_dict(dbdata)
    new_servers = set()
    servers = defaultdict(set)
    devices = defaultdict(set)
    counts = defaultdict(int)

    for method, args, kwargs in dbcalls:
        if method == "add_device":
            info = args[0]
            servers[method].add(info.server)
            if not info.server.lower() in old_servers:
                new_servers.add(info.server)
            n = 1
        elif "device_property" in method:
            n = len(args[1])
            devices[method].add(args[0].upper())
        elif "attribute_property" in method:
            n = sum(len(ps) for attr, ps in args[1].items())
            devices[method].add(args[0].upper())
        elif "property" in method:
            n = len(args[1])
        else:
            n = 1
        counts[method] += n

    messages = {
        "add_device": (green, "Add %%d devices to %d servers." %
                       len(servers["add_device"])),
        "delete_device": (red, "Delete %d devices."),
        "put_device_property": (
            yellow, "Add/change %%d device properties in %d devices." %
            len(devices["put_device_property"])),
        "delete_device_property": (
            red, "Delete %%d device properties from %d devices." %
            len(devices["delete_device_property"])),
        "put_device_attribute_property": (
            yellow, "Add/change %%d device attribute properties in %d devices." %
            len(devices["put_device_attribute_property"])),
        "delete_device_attribute_property": (
            red, "Delete %%d device attribute properties from %d devices.",
            len(devices["delete_device_attribute_property"])),
        "put_class_property": (yellow, "Add/change %d class properties."),
        "delete_class_property": (red, "Delete %d class properties."),
        "put_class_attribute_property": (
            yellow, "Add/change %d class attribute properties"),
        "delete_class_attribute_property": (
            red, "Delete %d class attribute properties."),
        "put_device_alias": (green, "Add/change %d device aliases"),
        "delete_device_alias": (red, "Delete %d device aliases")
    }

    summary = []
    if new_servers:
        summary.append(green("Add %d servers." % len(new_servers)))
    for method in methods:
        if method in counts:
            color, message = messages[method]
            summary.append(color(message % counts[method]))

    return summary


def get_device(db, devname, data, skip_protected=True):

    """Returns all relevant DB information about a given device:
    alias (if any), properties, attribute properties"""

    dev = {}

    try:
        alias = db.get_alias_from_device(devname)
        dev["alias"] = alias
    except PyTango.DevFailed:
        pass

    # Properties
    properties = {}
    db_props = db.get_device_property_list(devname, "*")
    if db_props:
        props = db.get_device_property(devname, list(db_props))
        for prop, value in props.items():
            # We'll ignore "protected" properties unless they are present
            # in the input data (in that case we want to show that
            # they are changed)
            if (not (skip_protected and is_protected(prop))
                    or prop in data.get("properties", {})):
                value = [str(v) for v in value]  # is this safe?
                properties[prop] = value
        dev["properties"] = properties

    # Attribute properties
    # Seems impossible* to get the full list of defined attribute
    # properties through the API so we'll have to make do with
    # the attributes we know about.
    # OTOH, usually if the attribute config changes, it's because
    # a user has set e.g. the format, and then we should not just
    # remove it, right?
    # (* It is possible, just not through the DB API. See the
    #    "DbMySqlSelect" command on the db device.)
    attribute_properties = {}
    attr_props = data.get("attribute_properties")
    if attr_props:
        dbprops = db.get_device_attribute_property(devname,
                                                   attr_props.keys())
        new_attr_props = data.get("attribute_properties", {})
        for attr, props in dbprops.items():
            attr_props = dict(
                (prop, [str(v) for v in values])
                for prop, values in props.items()
                if (not (skip_protected and is_protected(prop, True))
                    or prop in new_attr_props[attr])
            )  # whew!
            if attr_props:
                attribute_properties[attr] = attr_props
        if attribute_properties:
            dev["attribute_properties"] = attribute_properties

    return dev


def get_dict_from_db(db, data, narrow=False, skip_protected=True):

    """Takes a data dict, checks if any if the definitions are already
    in the DB and returns a dict describing them.

    By default it includes all devices for each server+class, use the
    'narrow' flag to limit to the devices present in the input data.
    """

    # This is where we'll collect all the relevant data
    dbdict = SetterDict()
    moved_devices = defaultdict(list)

    # Devices that are already defined somewhere else
    for server, inst, clss, device in get_devices_from_dict(
            data.get("servers", {})):
        try:
            devinfo = db.get_device_info(device)
            srvname = "%s/%s" % (server, inst)
            if devinfo.ds_full_name != srvname:
                moved_devices[devinfo.ds_full_name].append((clss, device))

        except PyTango.DevFailed:
            pass

    # Servers
    for srvr, insts in data.get("servers", {}).items():
        for inst, classes in insts.items():
            for clss, devs in classes.items():
                if narrow:
                    devices = devs.keys()
                else:
                    srv_full_name = "%s/%s" % (srvr, inst)
                    devices = db.get_device_name(srv_full_name, clss)
                for device in devices:
                    new_props = devs.get(device, {})
                    db_props = get_device(db, device, new_props, skip_protected)
                    dbdict.servers[srvr][inst][clss][device] = db_props

    # Classes
    for class_name, cls in data.get("classes", {}).items():
        props = cls.get("properties", {}).keys()
        for prop, value in db.get_class_property(class_name, props).items():
            if value:
                value = [str(v) for v in value]
                dbdict.classes[class_name].properties[prop] = value

        attr_props = cls.get("attribute_properties")
        if attr_props:
            dbprops = db.get_class_attribute_property(class_name,
                                                      attr_props.keys())
            for attr, props in dbprops.items():
                props = dict((prop, [str(v) for v in values])
                             for prop, values in props.items())
                dbdict.classes[class_name].attribute_properties[attr] = props

    return dbdict.to_dict(), moved_devices


def find_empty_servers(db, data):
    "Find any servers in the data that contain no devices, and remove them"
    servers = ["%s/%s" % (srv, inst)
               for srv, insts in data["servers"].items()
               for inst in insts.keys()]
    return [server for server in servers
            if all(d.lower().startswith('dserver/')
                   for d in db.get_device_class_list(server))]


def get_device_property_values(dbproxy, device, name="*",
                               include_subdevices=False):
    query = ("SELECT name, value FROM property_device "
             "WHERE device = '%s' AND name LIKE '%s'")
    _, result = dbproxy.DbMySqlSelect(
        query % (device, name.replace("*", "%")))
    data = defaultdict(list)
    for prop, row in izip(result[::2], result[1::2]):
        if prop != "__SubDevices" or include_subdevices:
            data[prop].append(row)
    return data


def get_device_attribute_property_values(dbproxy, device, name="*"):
    query = ("SELECT attribute, name, value FROM property_attribute_device "
             "WHERE device = '%s' AND name LIKE '%s'")
    _, result = dbproxy.DbMySqlSelect(
        query % (device, name.replace("*", "%")))
    data = AppendingDict()
    for attr, prop, row in izip(result[::3], result[1::3], result[2::3]):
        data[attr][prop] = row
    return data


def get_devices_for_class(dbproxy, clss):
    query = ("SELECT name FROM device WHERE class LIKE '%s'")
    _, result = dbproxy.DbMySqlSelect(query % clss.replace("*", "%"))
    return result


def get_devices_by_name_and_class(dbproxy, name, clss="*"):
    query = ("SELECT name FROM device WHERE name LIKE '%s' "
             "AND class LIKE '%s'")
    _, result = dbproxy.DbMySqlSelect(
        query % (name.replace("*", "%"), clss.replace("*", "%")))
    return result


def nwise(it, n):
    "[s_0, s_1, ...] => [(s_0, ..., s_(n-1)), (s_n, ... s_(2n-1)), ...]"
    return izip(*[islice(it, i, None, n) for i in xrange(n)])


def get_servers_with_filters(dbproxy, server="*", clss="*", device="*",
                             properties=True, attribute_properties=True,
                             aliases=True, dservers=False):
    """
    A performant way to get servers and devices in bulk from the DB
    by direct SQL statements and joins, instead of e.g. using one
    query to get the properties of each device.

    TODO: are there any length restrictions on the query results? In
    that case, use limit and offset to get page by page.
    """

    import sys
    from time import time

    server = server.replace("*", "%")  # mysql wildcards
    clss = clss.replace("*", "%")
    device = device.replace("*", "%")

    devices = AppendingDict()

    if properties:
        # Get all relevant device properties
        query = (
            "SELECT device, property_device.name, property_device.value" +
            " FROM property_device INNER JOIN device ON property_device.device = device.name" +
            " WHERE server LIKE '%s' AND class LIKE '%s' AND device LIKE '%s'")
        if not dservers:
            query += " AND class != 'DServer'"
        _, result = dbproxy.DbMySqlSelect(query % (server, clss, device))
        for d, p, v in nwise(result, 3):
            devices[d.upper()].properties[p] = v

    if attribute_properties:
        # Get all relevant attribute properties
        query = (
            "SELECT device, attribute, property_attribute_device.name, property_attribute_device.value" +
            " FROM property_attribute_device INNER JOIN device ON property_attribute_device.device = device.name" +
            " WHERE server LIKE '%s' AND class LIKE '%s' AND device LIKE '%s'")
        if not dservers:
            query += " AND class != 'DServer'"
        _, result = dbproxy.DbMySqlSelect(query % (server, clss, device))
        for d, a, p, v in nwise(result, 4):
            devices[d.upper()].attribute_properties[a][p] = v

    devices = devices.to_dict()

    # dump relevant servers
    query = (
        "SELECT server, class, name, alias FROM device" +
        (" WHERE server LIKE '%s' AND class LIKE '%s' AND name LIKE '%s'"
         % (server, clss, device)))
    if not dservers:
        query += " AND class != 'DServer'"
    _, result = dbproxy.DbMySqlSelect(query)

    # combine all the information we have
    servers = SetterDict()
    for s, c, d, a in nwise(result, 4):
        srv, inst = s.split("/")
        device = devices.get(d.upper(), {})
        if a and aliases:
            device["alias"] = a
        servers[srv][inst][c][d.upper()] = device

    return servers
