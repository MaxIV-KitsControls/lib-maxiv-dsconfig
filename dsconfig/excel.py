"""
Routines for reading an Excel file containing server, class and device definitions,
producing a file in the TangoDB JSON format.
"""

from datetime import datetime
import json
import os
import re
import sys
#from traceback import format_exc

from utils import find_device
from appending_dict import AppendingDict
from utils import CaselessDict

MODE_MAPPING = CaselessDict({"ATTR": "DynamicAttributes",
                             "CMD": "DynamicCommands",
                             "STATE": "DynamicStates",
                             "STATUS": "DynamicStatus"})

ATTRIBUTE_PROPERTY_NAMES = ["label", "format",
                            "min_value", "min_alarm", "min_warning",
                            "max_value", "min_alarm", "min_warning",
                            "unit", "polling_period", "change_event",
                            "description", "mode"]


def get_properties(row):

    "Find property definitions on a row"

    prop_dict = AppendingDict()

    # "Properties" column
    if "properties" in row:
        properties = row["properties"]
        try:
            for prop in properties.split(";"):
                name, value = prop.split("=")
                prop_dict[name.strip()] = value.strip()
        except ValueError:
            raise ValueError("could not parse Properties")

    # "Property:xyz" columns
    for col_name, value in row.items():
        match = re.match("property:(.*)", col_name, re.IGNORECASE)
        if match and value:
            name, = match.groups()
            if isinstance(value, float):    # TODO: numeric values become floats, but what if we only want integers?
                value = str(value)
            prop_dict[name] = value.strip()

    return prop_dict


def get_dynamic(row):
    "Find dynamic definitions on a row"

    prop_dict = AppendingDict()

    try:
        formula = row["formula"].strip()
        if "type" in row:
            # TODO: Sanity check type?
            formula = "%s(%s)" % (row["type"], formula)
        check_formula(formula)
        mode = row["mode"]
        if mode.lower() == "status":
            dyn = formula
        else:
            dyn = "%s=%s" % (row["name"], formula)
        prop_dict[MODE_MAPPING[mode]] = dyn
    except KeyError as e:
        raise ValueError("Problem with formula: %s" % e)

    return prop_dict


def make_db_name(name):
    "convert a Space Separated Name into a lowercase, underscore_separated_name"
    return name.strip().lower().replace(" ", "_")


def get_config(row):
    "WIP"
    prop_dict = AppendingDict()

    # "Cfg:attribute" columns
    for col_name, value in row.items():
        # match = re.match("cfg:(.*)", col_name, re.IGNORECASE)
        # if match and value:
        #     attr_name, = match.groups()
        #     name = make_db_name(name)
        #     prop_dict[name] = value.strip()

        # Pick up columns named after attribute properties
        db_colname = make_db_name(col_name)
        attr = row["attribute"].strip()
        if db_colname in ATTRIBUTE_PROPERTY_NAMES:
            prop_dict[attr][db_colname] = [value]

    return prop_dict


def check_formula(formula):
    "Syntax check a dynamic formula."
    compile(formula, "<stdin>", "single")


def check_device_format(devname):
    """
    Verify that a device name is of the correct form (three parts separated by slashes,
    only letters, numbers, dashes and underscores allowed.)
    Note: We could put more logic here to make device names
          conform to a standard.
    """
    device_pattern = "^[\w-]+/[\w-]+/[\w-]+$"
    if not re.match(device_pattern, devname):
        raise ValueError("device name '%s' not valid" % devname)


def format_server_instance(row):
    "Format a server/instance string, handling numeric instance names"
    instance = row["instance"]
    if isinstance(instance, float):    # numeric values become floats
        instance = str(int(instance))  # but we want integers
    return "%s/%s" % (row["server"], instance)


def convert(rows, definitions, skip=True, dynamic=False, config=False):

    "Update a dict of definitions from data"

    errors = []
    column_names = rows[0]

    def handle_error(i, msg):
        if skip:
            errors.append((i, msg))
        else:
            raise

    for i, row_ in enumerate(rows[1:]):
        try:
            # The plan is to try to find all information on the
            # line, raising exceptions if there are unrecoverable
            # problems. Those are caught and reported.

            # Filter out empty columns
            row = CaselessDict(dict((str(name), col)
                                    for name, col in zip(column_names, row_) if col))

            # Skip empty lines
            if not row:
                continue

            # Target of the properties; device or class?
            if "device" in row:
                check_device_format(row["device"])
                try:
                    # full device definition
                    srvr = format_server_instance(row)
                    target = definitions.servers[srvr][row["class"]][row["device"]]
                except KeyError:
                    # is the device already defined?
                    target, _ = find_device(definitions, row["device"])
            else:  # Class
                target = definitions.classes[row["class"]]

            if dynamic:
                props = get_dynamic(row)
                if props:
                    target.properties = props
            elif config:
                attr_props = get_config(row)
                if attr_props:
                    target.attribute_properties = attr_props
            else:
                props = get_properties(row)
                if props:
                    target.properties = props

        except KeyError as ke:
            #handle_error(i, "insufficient data (%s)" % ke)
            pass
        except ValueError as ve:
            handle_error(i, "Error: %s" % ve)
        except SyntaxError as se:
            # TODO: do something here to show more info about the error
            #ex_type, ex, tb = sys.exc_info()
            #"\n".join(format_exc(ex).splitlines()[-3:]
            handle_error(i, "SyntaxError: %s" % se)

    return errors


def print_errors(errors):
    if errors:
        print >> sys.stderr, "%d lines skipped" % len(errors)
        for err in errors:
            line, msg = err
            print >> sys.stderr, "%d: %s" % (line + 1, msg)


def xls_to_dict(xls_filename, pages=None, skip=False):

    """Make JSON out of an XLS sheet of device definitions."""


    import xlrd

    xls = xlrd.open_workbook(xls_filename)
    definitions = AppendingDict()

    if not pages:
        pages = xls.sheet_names()


    for page in pages:


        print >>sys.stderr, "\nPage: %s" % page
        sheet = xls.sheet_by_name(page)
        rows = [sheet.row_values(i)
                for i in xrange(sheet.nrows)]

        errors = convert(rows, definitions, skip=skip,
                         dynamic=(page == "Dynamics"),
                         config=(page == "ParamConfig"))
        print_errors(errors)

    return definitions


def get_stats(defs):
    "Calculate some numbers"

    servers = set()
    instances = set()
    classes = set()
    devices = set()

    for srvr_inst, clss in defs.servers.items():
        server, instance = srvr_inst.split("/")
        servers.add(server)
        instances.add(instance)
        for clsname, devs in clss.items():
            classes.add(clsname)
            for devname, dev in devs.items():
                devices.add(devname)

    return {"servers": len(servers), "instances": len(instances),
            "classes": len(classes), "devices": len(devices)}


def main():
    from optparse import OptionParser

    usage = "usage: %prog [options] XLS [PAGE1, PAGE2, ...]"
    parser = OptionParser(usage=usage)
    parser.add_option("-t", "--test", action="store_true",
                      dest="test", default=False,
                      help="just test, produce no JSON")
    parser.add_option("-q", "--quiet", action="store_false",
                      dest="verbose", default=True,
                      help="don't print errors to stdout")
    parser.add_option("-f", "--fatal", action="store_false",
                      dest="skip", default=True,
                      help="don't skip, treat any parsing error as fatal")

    options, args = parser.parse_args()
    if len(args) < 1:
        sys.exit("You need to give an XLS file as argument.")
    filename = args[0]
    pages = args[1:]

    data = xls_to_dict(filename, pages, skip=options.skip)
    metadata = dict(
        _title="MAX-IV Tango JSON intermediate format",
        _source=os.path.split(sys.argv[1])[-1],
        _version=1,
        _date=str(datetime.now()))
    data.update(metadata)

    if not options.test:
        print json.dumps(data, indent=4)
        outfile = open('config.json', 'w')
        json.dump(data, outfile, indent=4)

    stats = get_stats(data)

    print >>sys.stderr, ("\n"
        "Total: %(servers)d servers, %(instances)d instances, "
        "%(classes)d classes and %(devices)d devices defined.") % stats


if __name__ == "__main__":
    main()
