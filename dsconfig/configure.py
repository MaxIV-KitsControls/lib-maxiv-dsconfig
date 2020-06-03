"""
Functionality for configuring a Tango DB from a dsconfig file
"""

from collections import defaultdict
from functools import partial

import tango

from .appending_dict.caseless import CaselessDictionary
from .tangodb import SPECIAL_ATTRIBUTE_PROPERTIES, is_protected
from .utils import ObjectWrapper


def check_attribute_property(propname):
    # Is this too strict? Do we ever need non-standard attr props?
    if (not propname.startswith("_")
            and propname not in SPECIAL_ATTRIBUTE_PROPERTIES):
        raise KeyError("Bad attribute property name: %s" % propname)
    return True


def update_properties(db, parent, db_props, new_props,
                      attribute=False, cls=False,
                      delete=True, ignore_case=False, strict_attr_props=True):
    """
    Updates properties in DB. Covers both device and class
    properties/attribute properties.

    'parent' is the name of the containing device or class.
    """
    if ignore_case:
        caseless_db_props = CaselessDictionary(db_props)
        caseless_new_props = CaselessDictionary(new_props)
    else:
        caseless_db_props = db_props
        caseless_new_props = new_props
    # Figure out what's going to be added/changed or removed
    if attribute:
        added_props = defaultdict(dict)
        # For attribute properties we need to go one step deeper into
        # the dict, since each attribute can have several properties.
        # A little messy, but at least it's consistent.
        for attr, props in list(new_props.items()):
            for prop, value in list(props.items()):
                if ignore_case:
                    orig = CaselessDictionary(caseless_db_props.get(attr, {})).get(prop)
                else:
                    orig = caseless_db_props.get(attr, {}).get(prop)
                if value and value != orig and (not strict_attr_props
                                                or check_attribute_property(prop)):
                    added_props[attr][prop] = value
        removed_props = defaultdict(dict)
        for attr, props in list(db_props.items()):
            for prop in props:
                if ignore_case:
                    new = CaselessDictionary(new_props.get(attr, {})).get(prop)
                else:
                    new = new_props.get(attr, {}).get(prop)
                if (new is None and not is_protected(prop, True)) or new == []:
                    # empty list forces removal of "protected" properties
                    removed_props[attr][prop] = value
    else:
        added_props = {}
        for prop, value in list(new_props.items()):
            old_value = caseless_db_props.get(prop, [])
            if value and value != old_value:
                added_props[prop] = value
        removed_props = {}
        for prop, value in list(db_props.items()):
            new_value = caseless_new_props.get(prop)
            if (new_value is None and not is_protected(prop)) or new_value == []:
                # empty list forces removal of "protected" properties
                removed_props[prop] = value

    # Find the appropriate DB method to call. Thankfully the API is
    # consistent here.
    db_method_ending = (("class" if cls else "device") +
                        ("_attribute" if attribute else "") + "_property")
    put_method = getattr(db, "put_" + db_method_ending)
    delete_method = getattr(db, "delete_" + db_method_ending)

    # Do it!
    if delete and removed_props:
        delete_method(parent, removed_props)
    if added_props:
        put_method(parent, added_props)

    return added_props, removed_props


def update_server(db, server_name, server_dict, db_dict,
                  update=False, ignore_case=False,
                  difactory=tango.DbDevInfo, strict_attr_props=True):
    """
    Creates/removes devices for a given server. Optionally
    ignores removed devices, only adding new and updating old ones.
    """

    if ignore_case:
        db_dict = CaselessDictionary(db_dict)

    for class_name, cls in list(server_dict.items()):  # classes
        if ignore_case:
            cls = CaselessDictionary(cls)
        removed_devices = [dev for dev in db_dict.get(class_name, {})
                           if dev not in cls
                           # never remove dservers
                           and not class_name.lower() == "dserver"]
        added_devices = list(cls.items())
        if not update:
            for device_name in removed_devices:
                db.delete_device(device_name)

        for device_name, dev in added_devices:
            if ignore_case:
                devs = CaselessDictionary(db_dict.get(class_name, {}))
            else:
                devs = db_dict.get(class_name, {})
            if device_name not in devs:
                devinfo = difactory()
                devinfo.server = server_name
                devinfo._class = class_name
                devinfo.name = device_name
                db.add_device(devinfo)

            update_device(db, device_name, devs.get(device_name, {}),
                          dev, update=update, ignore_case=ignore_case,
                          strict_attr_props=strict_attr_props)

    return added_devices, removed_devices


def update_device_or_class(db, name, db_dict, new_dict,
                           cls=False, update=False, ignore_case=False,
                           strict_attr_props=True):
    """
    Configure a device or a class
    """

    # Note: if the "properties" key is missing, we'll just ignore any
    # existing properties in the DB. Ditto for attribute_properties.
    # To remove all existing properties, it should be an empty dict.

    if "properties" in new_dict:
        db_props = db_dict.get("properties", {})
        new_props = new_dict["properties"]
        update_properties(db, name, db_props, new_props, cls=cls,
                          delete=not update, ignore_case=ignore_case)

    if "attribute_properties" in new_dict:
        db_attr_props = db_dict.get("attribute_properties", {})
        new_attr_props = new_dict["attribute_properties"]
        update_properties(db, name, db_attr_props, new_attr_props,
                          attribute=True, cls=cls, delete=not update,
                          ignore_case=ignore_case,
                          strict_attr_props=strict_attr_props)

    # device aliases
    if not cls:
        if "alias" in new_dict and new_dict["alias"] != db_dict.get("alias"):
            db.put_device_alias(name, new_dict["alias"])
        elif not update and ("alias" not in new_dict and "alias" in db_dict):
            db.delete_device_alias(db_dict["alias"])


# nicer aliases
update_device = partial(update_device_or_class, cls=False)
update_class = partial(update_device_or_class, cls=True)


def configure(data, dbdata, update=False, ignore_case=False,
              strict_attr_props=True):
    """
    Takes an input data dict and the relevant current DB data.  Returns
    the DB calls needed to bring the Tango DB to the state described
    by 'data'.  The 'update' flag means that servers/devices are not
    removed, only added or changed. If the 'ignore_case' flag is True,
    the names of servers, devices and properties will be treated as
    caseless.

    Note: This function does *not* itself modify the Tango DB. It passes a
    "fake" database object around that just records what the various other
    functions do to it, and then returns the list of calls made.
    """

    db = ObjectWrapper()

    for servername, serverdata in list(data.get("servers", {}).items()):
        for instname, instdata in list(serverdata.items()):
            dbinstdata = (dbdata.get("servers", {})
                          .get(servername, {})
                          .get(instname, {}))
            added, removed = update_server(
                db, "%s/%s" % (servername, instname),
                instdata, dbinstdata, update, ignore_case,
                strict_attr_props=strict_attr_props)

    for classname, classdata in list(data.get("classes", {}).items()):
        dbclassdata = dbdata.get("classes", {}).get(classname, {})
        update_class(db, classname, dbclassdata, classdata, update=update)

    return db.calls
