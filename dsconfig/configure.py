"""Functionality for configuring a Tango DB from a dsconfig file"""

from functools import partial

import PyTango

from utils import ObjectWrapper
from tangodb import SPECIAL_ATTRIBUTE_PROPERTIES, is_protected


def check_attribute_property(propname):
    # Is this too strict? Do we ever need non-standard attr props?
    if propname not in SPECIAL_ATTRIBUTE_PROPERTIES:
        raise KeyError("Bad attribute property name: %s" % propname)
    return True


def update_properties(db, parent, db_props, new_props,
                      attr=False, cls=False, delete=True):
    """
    Updates properties in DB. Covers both device and class
    properties/attribute properties.

    'parent' is the name of the containing device or class.
    """

    # Figure out what's going to be added/changed or removed
    if attr:
        # For attribute properties we need to go one step deeper into
        # the dict, since each attribute can have several properties.
        # A little messy, but at least it's consistent.
        added_props = {}
        for attr, props in new_props.items():
            for prop, value in props.items():
                orig = db_props.get(attr, {}).get(prop)
                if value and value != orig and check_attribute_property(prop):
                    added_props[attr] = props
        removed_props = {}
        for attr, props in db_props.items():
            for prop in props:
                new = new_props.get(attr, {}).get(prop)
                if not new and not is_protected(prop, True):
                    removed_props[prop] = value
    else:
        added_props = {}
        for prop, value in new_props.items():
            old_value = db_props.get(prop, [])
            if value and value != old_value:
                added_props[prop] = value
        removed_props = {}
        for prop, value in db_props.items():
            new_value = new_props.get(prop)
            if not new_value and not is_protected(prop):
                removed_props[prop] = value

    # Find the appropriate DB method to call. Thankfully the API is
    # consistent here.
    db_method_ending = (("class" if cls else "device") +
                        ("_attribute" if attr else "") + "_property")
    put_method = getattr(db, "put_" + db_method_ending)
    delete_method = getattr(db, "delete_" + db_method_ending)

    # Do it!
    if delete and removed_props:
        delete_method(parent, removed_props)
    if added_props:
        put_method(parent, added_props)

    return added_props, removed_props


def update_server(db, difactory, server_name, server_dict, db_dict,
                  update=False):

    """Creates/removes devices for a given server. Optionally
    ignores removed devices, only adding new and updating old ones."""

    for class_name, cls in server_dict.items():  # classes
        removed_devices = [dev for dev in db_dict.get(class_name, {})
                           if dev not in cls]
        added_devices = cls.items()
        if not update:
            for device_name in removed_devices:
                db.delete_device(device_name)

        for device_name, dev in added_devices:
            if device_name not in db_dict.get(class_name, {}):
                devinfo = difactory()
                devinfo.server = server_name
                devinfo._class = class_name
                devinfo.name = device_name
                db.add_device(devinfo)

            update_device(db, device_name,
                          db_dict.get(class_name, {}).get(device_name, {}),
                          dev, update=update)

    return added_devices, removed_devices


def update_device_or_class(db, name, db_dict, new_dict,
                           cls=False, update=False):

    "Configure a device or a class"

    # Note: if the "properties" key is missing, we'll just ignore any
    # existing properties in the DB. Ditto for attribute_properties.

    if "properties" in new_dict:
        db_props = db_dict.get("properties", {})
        new_props = new_dict["properties"]
        update_properties(db, name, db_props, new_props, cls=cls,
                          delete=not update)
    if "attribute_properties" in new_dict:
        db_attr_props = db_dict.get("attribute_properties", {})
        new_attr_props = new_dict["attribute_properties"]
        update_properties(db, name, db_attr_props, new_attr_props,
                          attr=True, cls=cls, delete=not update)


# nicer aliases
update_device = partial(update_device_or_class, cls=False)
update_class = partial(update_device_or_class, cls=True)


def configure(data, dbdata, update=False):

    """Takes an input data dict and the relevant current DB data.  Returns
    the DB calls needed to bring the Tango DB to the state described
    by 'data'.  The 'update' flag means that servers/devices are not
    removed, only added or changed.

    Note: This function does *not* itself modify the Tango DB. It passes a
    "fake" database object around that just records what the various other
    functions do to it, and then returns the list of calls made.
    """

    db = ObjectWrapper()

    for servername, serverdata in data.get("servers", {}).items():
        for instname, instdata in serverdata.items():
            added, removed = update_server(
                db, PyTango.DbDevInfo, "%s/%s" % (servername, instname),
                instdata, (dbdata.get("servers", {})
                           .get(servername, {})
                           .get(instname, {})), update)

    for classname, classdata in data.get("classes", {}).items():
        update_class(db, classname, dbdata.get("classes", {}).get(classname, {}),
                     classdata, update=update)

    return db.calls
