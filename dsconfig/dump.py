"""
Takes a list of server/class/devices (optionally with wildcards)
and prints the current configuration for those in JSON dsconfig format.

$ python -m dsconfig.dump server:TangoTest/1 > result.json
$ python -m dsconfig.dump device:sys/tg_test/1 device:sys/tg_test/2
...

"""

from .tangodb import get_servers_with_filters, get_classes_properties
from .appending_dict import SetterDict
import PyTango


def get_db_data(db, patterns=None, class_properties=False, **options):

    # dump TANGO database into JSON. Optionally filter which things to include
    # (currently only "positive" filters are possible; you can say which
    # servers/classes/devices to include, but you can't exclude selectively)
    # By default, dserver devices aren't included!

    dbproxy = PyTango.DeviceProxy(db.dev_name())
    data = SetterDict()

    if not patterns:
        # the user did not specify a pattern, so we will dump *everything*
        servers = get_servers_with_filters(
            dbproxy, **options)
        data.servers.update(servers)
        if class_properties:
            classes = get_classes_properties(dbproxy)
            data.classes.update(classes)
    else:
        # go through all patterns and fill in the data
        for pattern in patterns:
            prefix, pattern = pattern.split(":")
            kwargs = {prefix: pattern}
            kwargs.update(options)
            servers = get_servers_with_filters(dbproxy, **kwargs)
            data.servers.update(servers)
            if class_properties:
                classes = get_classes_properties(dbproxy,  server=pattern)
                data.classes.update(classes)
    return data.to_dict()


def main():

    import json
    from optparse import OptionParser

    usage = "Usage: %prog [term:pattern term2:pattern2...]"
    parser = OptionParser(usage=usage)
    parser.add_option("-p", "--no-properties", dest="properties",
                      action="store_false", default=True,
                      help="Exclude device properties")
    parser.add_option("-a", "--no-attribute-properties",
                      dest="attribute_properties",
                      action="store_false", default=True,
                      help="Exclude attribute properties")
    parser.add_option("-l", "--no-aliases", dest="aliases",
                      action="store_false", default=True,
                      help="Exclude device aliases")
    parser.add_option("-d", "--dservers", dest="dservers",
                      action="store_true", help="Include DServer devices")
    parser.add_option("-s", "--subdevices", dest="subdevices",
                      action="store_true", default=False,
                      help="Include __SubDevices property")
    parser.add_option("-c", "--class-properties",
                      dest="class_properties",
                      action="store_true", default=False,
                      help="Include class properties")

    options, args = parser.parse_args()

    db = PyTango.Database()
    dbdata = get_db_data(db, args,
                         properties=options.properties,
                         class_properties=options.class_properties,
                         attribute_properties=options.attribute_properties,
                         aliases=options.aliases, dservers=options.dservers,
                         subdevices=options.subdevices)
    print(json.dumps(dbdata, ensure_ascii=False, indent=4, sort_keys=True))


if __name__ == "__main__":
    main()
