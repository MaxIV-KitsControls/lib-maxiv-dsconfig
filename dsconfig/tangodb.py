import PyTango

from appending_dict import AppendingDict
from utils import get_devices_from_dict


# These are special properties that we'll ignore for now
PROTECTED_PROPERTIES = [
    "polled_attr", "logging_level", "logging_target"
]


SPECIAL_ATTRIBUTE_PROPERTIES = [
    "label", "format", "unit", "min_value", "min_alarm", "min_warning",
    "max_value", "min_alarm", "min_warning", "abs_change", "rel_change",
    "event_period", "archive_abs_change", "archive_rel_change",
    "archive_period", "description", "mode"
]


def is_protected(prop, attr=False):
    """There are certain properties that need special treatment as they
    are handled in particular ways by Tango. In general, we don't want to
    remove these if they exist, but we do allow overwriting them."""
    if attr:
        # Attribute config properties
        return prop.startswith("_") or prop in SPECIAL_ATTRIBUTE_PROPERTIES
    else:
        return prop.startswith("_") or prop in PROTECTED_PROPERTIES


def get_device_properties(db, devname, data):
    dev = AppendingDict()
    db_props = db.get_device_property_list(devname, "*")
    # Properties
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
    moved_devices = []

    # Devices that are already defined somewhere else
    for server, clss, device in get_devices_from_dict(data.get("servers", {})):
        try:
            devinfo = db.get_device_info(device)
            if devinfo.ds_full_name != server:
                moved_devices.append((devinfo.name, devinfo.class_name,
                                      devinfo.ds_full_name))
            # TODO: check if any servers become empty
        except PyTango.DevFailed:
            pass

    # Servers
    for server_name, srvr in data.get("servers", {}).items():
        for class_name, cls in srvr.items():
            if narrow:
                devices = cls.keys()
            else:
                devices = db.get_device_name(server_name, class_name)

            for device_name in devices:
                dev = get_device_properties(db, device_name,
                                            cls.get(device_name, {}))
                dbdict.servers[server_name][class_name][device_name] = dev

    # Classes
    for class_name, cls in data.get("classes", {}).items():

        db_props = cls.get("properties", ())
        for prop, value in db.get_class_property(class_name, db_props).items():
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
