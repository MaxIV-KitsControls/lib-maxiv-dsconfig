import json
import sys

import tango

from .utils import (ObjectWrapper, decode_dict, get_dict_from_db,
                    RED, GREEN, YELLOW)


def delete_devices(db, dbdict, server, cls, devices):
    for devname in devices:
        if dbdict.servers[server][cls][devname]:
            db.delete_device(devname)
        else:
            print("no device", devname)


def delete_server(db, dbdict, servername, serverdata):
    for clsname, devices in list(serverdata.items()):
        delete_devices(db, dbdict, servername, clsname, list(devices.keys()))
    try:
        db.delete_server_info(servername)  # what does this do?
        db.delete_server(servername)
    except tango.DevFailed:
        # I'm not sure about this; sometimes deleting servers works
        # and sometimes not; should they be running? What's going on?
        # Anyway, the worst case scenario is that the servers are
        # still there but contain no devices...
        print("Removing server '%s' may have failed." % servername)


def delete_class(db, dbdict, classname):
    props = list(dbdict.classes[classname].properties.keys())
    if props:
        db.delete_class_property(classname, props)
    attr_props = list(dbdict.classes[classname].attribute_properties.keys())
    if attr_props:
        db.delete_class_attribute_property(classname, attr_props)


def main(json_file, write=False, db_calls=False):
    """
    Remove the devices and servers defined in the given file from the DB.
    """

    with open(json_file) as f:
        data = json.load(f, object_hook=decode_dict)

    db = tango.Database()
    dbdict = get_dict_from_db(db, data)  # check the current DB state

    # wrap the database (and fake it if we're not going to write)
    db = ObjectWrapper(db if write else None)

    # delete servers and devices
    for servername, serverdata in list(data.get("servers", {}).items()):
        if servername in dbdict.servers:
            delete_server(db, dbdict, servername, serverdata)

    # delete classes
    for classname, classdata in list(data.get("classes", {}).items()):
        if classname in dbdict.classes:
            delete_class(db, dbdict, classname)

    if db_calls:
        print("\nTango database calls:")
        for method, args, kwargs in db.calls:
            print(method, args)

    if db.calls:
        if write:
            print((
                    RED + "\n*** Data was written to the Tango DB ***"), file=sys.stderr)
        else:
            print(YELLOW + \
                  "\n*** Nothing was written to the Tango DB (use -w) ***", file=sys.stderr)
    else:
        print(GREEN + "\n*** No changes needed in Tango DB ***", file=sys.stderr)


if __name__ == "__main__":
    from optparse import OptionParser

    usage = "Usage: %prog [options] JSONFILE"
    parser = OptionParser(usage=usage)

    parser.add_option("-w", "--write", dest="write", action="store_true",
                      help="write to the Tango DB", metavar="WRITE")
    parser.add_option("-d", "--dbcalls", dest="dbcalls", action="store_true",
                      help="print out all db calls.")

    options, args = parser.parse_args()

    main(args[0], write=options.write, db_calls=options.dbcalls)
