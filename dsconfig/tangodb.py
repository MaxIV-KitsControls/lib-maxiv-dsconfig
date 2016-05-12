from collections import defaultdict
from itertools import izip

import PyTango

from appending_dict import AppendingDict
from dsconfig.utils import green, red, yellow


# These are special properties that we'll ignore for now
PROTECTED_PROPERTIES = [
    "polled_attr", "logging_level", "logging_target"
]


SPECIAL_ATTRIBUTE_PROPERTIES = [
    "label", "format", "unit", "min_value", "min_alarm", "min_warning",
    "max_value", "min_alarm", "min_warning", "abs_change", "rel_change",
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
        "delete_class_attribute_property"
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
    }

    summary = []
    if new_servers:
        summary.append(green("Add %d servers." % len(new_servers)))
    for method in methods:
        if method in counts:
            color, message = messages[method]
            summary.append(color(message % counts[method]))

    return summary


def get_device_properties(db, devname, data):
    dev = AppendingDict()

    # Properties
    db_props = db.get_device_property_list(devname, "*")
    if db_props:
        props = db.get_device_property(devname, list(db_props))
        for prop, value in props.items():
            # We'll ignore "protected" properties unless they are present
            # in the input data (in that case we want to show that they are changed)
            if not is_protected(prop) or prop in data.get("properties", {}):
                value = [str(v) for v in value]  # is this safe?
                dev.properties[prop] = value

    # Attribute properties
    # Seems impossible to get the full list of defined attribute
    # properties through the API so we'll have to make do with
    # the attributes we know about.
    attr_props = data.get("attribute_properties")
    if attr_props:
        dbprops = db.get_device_attribute_property(devname,
                                                   attr_props.keys())
        for attr, props in dbprops.items():
            props = dict((prop, [str(v) for v in values])
                         for prop, values in props.items())  # whew!
            if props:
                dev.attribute_properties[attr] = props
    return dev


def get_dict_from_db(db, data, narrow=False):

    """Takes a data dict, checks if any if the definitions are already
    in the DB and returns a dict describing them.

    By default it includes all devices for each server+class, use the
    'narrow' flag to limit to the devices present in the input data.
    """

    # This is where we'll collect all the relevant data
    dbdict = AppendingDict()
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
                    db_props = get_device_properties(db, device, new_props)
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
            if all(d.lower().startswith('dserver')
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
