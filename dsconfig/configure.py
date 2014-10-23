"""
Reads a JSON file in the right format, compares it with the current
state of the Tango DB, and generates the set of DB API commands needed
to get to the state described by the file. These commands can also
optionally be run.

Note that the granularity is on the top (server/class) level; servers
and classes not mentioned in the JSON file are ignored. However, any
devices, properties, etc belonging to the mentioned servers/classes in
the DB, but not present in the JSON file will be removed, unless the
--update flag is used.

If the "jsonpatch" module is installed, a "diff" representing the
changes will be printed. Inspecting this before writing to the DB
could prevent embarrassing mistakes.
"""

from collections import Mapping
from os import path
import sys
import json

from utils import (red, green, yellow,
                   ObjectWrapper, get_dict_from_db,
                   decode_dict, decode_pointer)

from appending_dict import AppendingDict
from excel import ATTRIBUTE_PROPERTY_NAMES

module_path = path.dirname(path.realpath(__file__))
SCHEMA_FILENAME = path.join(module_path, "schema/dsconfig.json")


def check_attribute_properties(attr_props):
    bad = {}  #AppendingDict()
    for attr, ap in attr_props.items():
        for prop, value in ap.items():
            if prop not in ATTRIBUTE_PROPERTY_NAMES:
                bad[attr] = prop
    return bad


def update_properties(db, parent, db_props, new_props,
                      attr=False, cls=False, delete=True):
    """
    Updates properties in DB. Covers both device and class
    properties/attribute properties.
    """

    # Figure out what's going to be added/changed or removed
    if attr:
        # For attribute properties we need to go one step deeper into
        # the dict, since each attribute can have several properties.
        # A little messy, but at least it's consistent.
        added_props = dict((prop, value)
                           for prop, value in new_props.items()
                           for attr_prop, value2 in value.items()
                           if db_props.get(prop, {}).get(attr_prop) != value2)
        removed_props = dict((prop, value)
                             for prop, value in db_props.items()
                             for attr_prop in value
                             if attr_prop not in new_props.get(prop, {}))
    else:
        added_props = dict((prop, value)
                           for prop, value in new_props.items()
                           if db_props.get(prop) != value)
        removed_props = dict((prop, value)
                             for prop, value in db_props.items()
                             if prop not in new_props)

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

    devinfo = difactory()
    devinfo.server = server_name

    for class_name, cls in server_dict.items():  # classes
        devinfo._class = class_name
        removed_devices = [dev for dev in db_dict[class_name]
                           if dev not in cls]
        added_devices = cls.items()

        if not update:
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
                                                   db_props, new_props,
                                                   delete=not update)
            if "attribute_properties" in dev:
                db_attr_props = (db_dict[class_name][device_name]
                                 ["attribute_properties"])
                new_attr_props = dev["attribute_properties"]
                added, removed = update_properties(db, device_name,
                                                   db_attr_props,
                                                   new_attr_props,
                                                   attr=True,
                                                   delete=not update)


def update_class(db, class_name, class_dict, db_dict, update=False):

    "Configure a class"

    if "properties" in class_dict:
        db_props = db_dict["properties"]
        new_props = class_dict["properties"]
        added, removed = update_properties(db, class_name, db_props,
                                           new_props, cls=True,
                                           delete=not update)
    if "attribute_properties" in class_dict:
        db_attr_props = db_dict["attribute_properties"]
        new_attr_props = class_dict["attribute_properties"]
        removed, added = update_properties(db, class_name, db_attr_props,
                                           new_attr_props, attr=True, cls=True,
                                           delete=not update)


def dump_value(value):
    "Make a string out of a value, for printing"
    if value is not None:
        if isinstance(value, Mapping):
            dump = json.dumps(value, indent=4)
            return dump
        return repr(value)
    else:
        return "None"  # should never happen?


def print_diff(dbdict, data, removes=True):

    "Print a (hopefully) human readable list of changes."

    # TODO: needs work, especially on multiline properties,
    # empty properties (should probably never be allowed but still)
    # and probably more corner cases. Also the output format could
    # use some tweaking.

    try:
        from collections import defaultdict
        import jsonpatch
        from jsonpointer import resolve_pointer, JsonPointerException

        ops = defaultdict(int)

        diff = jsonpatch.make_patch(dbdict, data)
        for d in diff:
            try:
                ptr = " > ".join(decode_pointer(d["path"]))
                if d["op"] == "replace":
                    print yellow("REPLACE:")
                    print yellow(ptr)
                    db_value = resolve_pointer(dbdict, d["path"])
                    print red(dump_value(db_value))
                    print green(dump_value(d["value"]))
                    ops["replace"] += 1
                if d["op"] == "add":
                    print green("ADD:")
                    print green(ptr)
                    if d["value"]:
                        print green(dump_value(d["value"]))
                    ops["add"] += 1
                if removes and d["op"] == "remove":
                    print red("REMOVE:")
                    print red(ptr)
                    value = resolve_pointer(dbdict, d["path"])
                    if value:
                        print red(dump_value(value))
                    ops["remove"] += 1
            except JsonPointerException as e:
                print " - Error parsing diff - report this!: %s" % e
        # # The following output is a bit misleading, removing for now
        # print "Total: %d operations (%d replace, %d add, %d remove)" % (
        #     sum(ops.values()), ops["replace"], ops["add"], ops["remove"])
        return diff
    except ImportError:
        print >>sys.stderr, ("'jsonpatch' module not available - "
                             "no diff printouts for you! (Try -d instead.)")


def validate_json(data):
    """Validate that a given dict is of the right form"""
    try:
        from jsonschema import validate, exceptions
        with open(SCHEMA_FILENAME) as schema_json:
            schema = json.load(schema_json)
        validate(data, schema)
    except ImportError:
        print >>sys.stderr, ("'jsonschema' not installed, could not "
                             "validate json file. You're on your own.")
    except exceptions.ValidationError as e:
        print >>sys.stderr, "JSON data does not match schema: %s" % e
        sys.exit(1)


def main():

    import PyTango
    from optparse import OptionParser

    usage = "Usage: %prog [options] JSONFILE"
    parser = OptionParser(usage=usage)

    parser.add_option("-w", "--write", dest="write", action="store_true",
                      help="write to the Tango DB", metavar="WRITE")
    parser.add_option("-u", "--update", dest="update", action="store_true",
                      help="don't remove things, only add/update",
                      metavar="UPDATE")
    parser.add_option("-q", "--quiet",
                      action="store_false", dest="verbose", default=True,
                      help="don't print actions to stdout")
    parser.add_option("-o", "--output", dest="output", action="store_true",
                      help="Output the relevant DB state as JSON.")
    parser.add_option("-d", "--dbcalls", dest="dbcalls", action="store_true",
                      help="print out all db calls.")
    parser.add_option("-v", "--no-validation", dest="validate", default=True,
                      action="store_false", help=("Skip JSON validation"))

    options, args = parser.parse_args()
    if len(args) == 0:
        data = json.load(sys.stdin, object_hook=decode_dict)
    else:
        json_file = args[0]
        with open(json_file) as f:
            data = json.load(f, object_hook=decode_dict)

    # Optional validation of the JSON file format.
    if options.validate:
        validate_json(data)

    # remove any metadata at the top level
    for key in data.keys():
        if key.startswith("_"):
            data.pop(key, None)

    db = PyTango.Database()
    dbdict, collisions = get_dict_from_db(db, data)

    if options.output:
        print json.dumps(dbdict, indent=4)

    # wrap the database to record calls (and fake it if not writing)
    db = ObjectWrapper(db if options.write else None)

    # remove devices already present in another server
    for dev, cls, srv in collisions:
        print >>sys.stderr, red("REMOVE (because of collision):")
        print >>sys.stderr, red(" > servers > %s > %s > %s" % (srv, cls, dev))
        db.delete_device(dev)  # this may not strictly be needed..?

    # Print out a nice diff
    if options.verbose:
        print_diff(dbdict, data, removes=not options.update)

    for servername, serverdata in data.get("servers", {}).items():
        update_server(db, PyTango.DbDevInfo, servername, serverdata,
                      dbdict["servers"][servername], options.update)
    for classname, classdata in data.get("classes", {}).items():
        update_class(db, classname, classdata,
                     dbdict["classes"][classname], options.update)

    if options.dbcalls:
        print "\nTango database calls:"
        for method, args, kwargs in db.calls:
            print method, args

    if db.calls:
        if options.write:
            print >>sys.stderr, red("\n*** Data was written to the Tango DB ***")
        else:
            print >>sys.stderr, yellow(
                "\n*** Nothing was written to the Tango DB (use -w) ***")
    else:
        print >>sys.stderr, green("\n*** No changes needed in Tango DB ***")


if __name__ == "__main__":
    main()
