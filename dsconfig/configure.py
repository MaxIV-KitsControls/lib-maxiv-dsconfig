from collections import Mapping
import sys
import json

import PyTango

from utils import (ADD, REMOVE, RED, GREEN, YELLOW, ENDC,
                   ObjectWrapper, get_dict_from_db,
                   decode_dict, decode_pointer)


def update_properties(db, parent, db_props, new_props,
                      attr=False, cls=False):
    """
    Updates properties in DB. Covers both device and class
    properties/attribute properties.
    """

    # Figure out what's going to be added/changed or removed
    added_props = dict((prop, value)
                       for prop, value in new_props.items()
                       if db_props.get(prop) != value)
    removed_props = dict((prop, value)
                         for prop, value in db_props.items()
                         if prop not in new_props)

    # Find the appropriate DB method to call. Thankfully the API is
    # pretty consistent here.
    db_method_ending = (("class" if cls else "device") +
                        ("_attribute" if attr else "") + "_property")
    put_method = getattr(db, "put_" + db_method_ending)
    delete_method = getattr(db, "delete_" + db_method_ending)

    # Do it!
    if removed_props:
        delete_method(parent, removed_props)
    if added_props:
        put_method(parent, added_props)

    return added_props, removed_props


def update_server(db, server_name, server_dict, db_dict):

    """Creates/removes devices for a given server."""

    devinfo = PyTango.DbDevInfo()
    devinfo.server = server_name

    for class_name, cls in server_dict.items():  # classes
        devinfo._class = class_name
        removed_devices = [dev for dev in db_dict[class_name]
                           if dev not in cls]
        added_devices = cls.items()

        for device_name in removed_devices:
            db.delete_device(device_name)

        for device_name, dev in added_devices:
            devinfo.name = device_name
            if device_name not in db_dict[class_name]:
                db.add_device(devinfo)

            if "properties" in dev:
                db_props = db_dict[class_name][device_name]["properties"]
                new_props = dev["properties"]
                added, removed = update_properties(db, device_name,
                                                   db_props, new_props)
            if "attribute_properties" in dev:
                db_attr_props = (db_dict[class_name][device_name]
                                 ["attribute_properties"])
                new_attr_props = dev["attribute_properties"]
                removed, added = update_properties(db, device_name,
                                                   db_attr_props,
                                                   new_attr_props, True)


def update_class(db, class_name, class_dict, db_dict):

    if "properties" in class_dict:
        db_props = db_dict["properties"]
        new_props = class_dict["properties"]
        added, removed = update_properties(db, class_name, db_props,
                                           new_props, False, True)
    if "attribute_properties" in class_dict:
        db_attr_props = db_dict["attribute_properties"]
        new_attr_props = class_dict["attribute_properties"]
        removed, added = update_properties(db, class_name, db_attr_props,
                                           new_attr_props, True, True)


def dump_value(value):
    "Make a string out of a value, for printing"
    if value:
        if isinstance(value, Mapping):
            dump = json.dumps(value, indent=4)
            return dump
        return str(value)
    else:
        return "None"  # should never happen?


def print_diff(dbdict, data):

    "Print a (hopefully) human readable list of changes."

    from collections import defaultdict
    import jsonpatch
    from jsonpointer import resolve_pointer

    ops = defaultdict(int)

    diff = jsonpatch.make_patch(dbdict, data)
    for d in diff:
        ptr = " > ".join(decode_pointer(d["path"]))
        if d["op"] == "replace":
            print "REPLACE:"
            print ptr
            db_value = resolve_pointer(dbdict, d["path"])
            print REMOVE + dump_value(db_value) + ENDC
            print ADD + str(d["value"]) + ENDC
            ops["replace"] += 1
        if d["op"] == "add":
            print "ADD:"
            print ptr
            if d["value"]:
                print ADD + dump_value(d["value"]) + ENDC
            ops["add"] += 1
        if d["op"] == "remove":
            print "REMOVE:"
            print ptr
            value = resolve_pointer(dbdict, d["path"])
            if value:
                print REMOVE + dump_value(value) + ENDC
            ops["remove"] += 1

    # # The following output is a bit misleading, removing for now
    # print "Total: %d operations (%d replace, %d add, %d remove)" % (
    #     sum(ops.values()), ops["replace"], ops["add"], ops["remove"])
    return diff


def main():

    from optparse import OptionParser

    usage = "Usage: %prog [options] JSONFILE"
    parser = OptionParser(usage=usage)

    parser.add_option("-w", "--write", dest="write", action="store_true",
                      help="write to the Tango DB", metavar="WRITE")
    parser.add_option("-q", "--quiet",
                      action="store_false", dest="verbose", default=True,
                      help="don't print actions to stdout")
    parser.add_option("-o", "--output", dest="output", action="store_true",
                      help="Output the relevant DB state as JSON.")
    parser.add_option("-d", "--dbcalls", dest="dbcalls", action="store_true",
                      help="print out all db calls.")

    options, args = parser.parse_args()
    if len(args) == 0:
        data = json.load(sys.stdin, object_hook=decode_dict)
    else:
        json_file = args[0]
        with open(json_file) as f:
            data = json.load(f, object_hook=decode_dict)

    for key in data.keys():
        if key.startswith("_"):
            data.pop(key, None)  # remove any metadata

    db = PyTango.Database()
    dbdict = get_dict_from_db(db, data)  # check the current DB state

    if options.output:
        print json.dumps(dbdict, indent=4)

    if options.verbose:
        try:
            print_diff(dbdict, data)
        except ImportError:
            print >>sys.stderr, ("'jsonpatch' module not available - "
                                 "no diff functionality for you!")

    # wrap the database to record calls (and fake it if not writing)
    db = ObjectWrapper(db if options.write else None)

    for servername, serverdata in data.get("servers", {}).items():
        update_server(db, servername, serverdata,
                      dbdict["servers"][servername])
    for classname, classdata in data.get("classes", {}).items():
        update_class(db, classname, classdata,
                     dbdict["classes"][classname])

    if options.dbcalls:
        print "\nTango database calls:"
        for method, args, kwargs in db.calls:
            print method, args

    if db.calls:
        if options.write:
            print >>sys.stderr, (
                RED + "\n*** Data was written to the Tango DB ***") + ENDC
        else:
            print >>sys.stderr, YELLOW +\
                "\n*** Nothing was written to the Tango DB (use -w) ***" + ENDC
    else:
        print >>sys.stderr, GREEN + "\n*** No changes needed in Tango DB ***" + ENDC


if __name__ == "__main__":
    main()
