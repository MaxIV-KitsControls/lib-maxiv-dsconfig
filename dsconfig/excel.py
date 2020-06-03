"""
Routines for reading an Excel file containing server, class and device definitions,
producing a file in the TangoDB JSON format.
"""

import json
import os
import re
import sys
from datetime import datetime

from .appending_dict import AppendingDict
from .tangodb import SPECIAL_ATTRIBUTE_PROPERTIES
from .utils import CaselessDict
from .utils import find_device

# from traceback import format_exc

MODE_MAPPING = CaselessDict({"ATTR": "DynamicAttributes",
                             "CMD": "DynamicCommands",
                             "STATE": "DynamicStates",
                             "STATUS": "DynamicStatus"})

TYPE_MAPPING = CaselessDict({"INT": int,
                             "FLOAT": float})


def get_properties(row):
    """
    Find property definitions on a row
    """

    prop_dict = AppendingDict()

    # "Properties" column
    # The cell value is expected to be on the form
    #   "property1=value1;property2=value2" etc
    # Note: In this case we cannot know the type of the value so we will
    # use the string as it is. This should be safe for e.g. numbers,
    # as long as the format of the string is correct
    if "properties" in row:
        properties = row["properties"]
        try:
            for prop in properties.split(";"):
                name, value = prop.split("=")
                # need to decode the string, otherwise any linebreaks
                # will be escaped.
                value = str(value) # .decode("string-escape")
                # Support inline multiline properties using "\n"
                prop_dict[name.strip()] = [v.strip()
                                           for v in value.split("\n")]
        except ValueError:
            raise ValueError("could not parse Properties")

    # "Property:xyz" and "Property(type):xyz columns
    # The main issue here is that spreadsheet programs treat numeric cells
    # as floats. If the number must be inserterd as an int, use the "(INT)"
    # modifier. There does not seem to be a way to force a numeric cell to
    # be interpreted as a string.
    for col_name, value in list(row.items()):
        match = re.match("property(?:\((.*)\))?:(.*)", col_name, re.IGNORECASE)
        if match and (value is not None):  # protect against zero, false...
            type_, name = match.groups()
            if type_:
                convert = TYPE_MAPPING[type_]
                values = [convert(value)]
            else:
                value = str(value)
                values = [v.strip() for v in value.split("\n")]
            prop_dict[name] = values

    return prop_dict


def get_attribute_properties(row):
    if "attribute" in row:
        attribute = row["attribute"]
        prop_dict = AppendingDict()
        if "attributeproperties" in row:
            properties = row["attributeproperties"]
            try:
                for prop in properties.split(";"):
                    name, value = prop.split("=")
                    name = name.strip()
                    if name not in SPECIAL_ATTRIBUTE_PROPERTIES:
                        raise ValueError(
                            "'%s' is not a valid attribute property" % name)
                    prop_dict[name.strip()] = [v.strip()
                                               for v in value.split("\n")]
            except ValueError:
                raise ValueError("could not parse AttributeProperties")

        for col_name, value in list(row.items()):
            match = re.match("attrprop:(.*)", col_name, re.IGNORECASE)
            if match and value:
                name, = match.groups()
                name = make_db_name(name.strip())
                if name not in SPECIAL_ATTRIBUTE_PROPERTIES:
                    raise ValueError("'%s' it not a valid attribute property"
                                     % name)
                value = str(value)
                values = [v.strip() for v in value.split("\n")]
                prop_dict[name] = values

        return {attribute: prop_dict}


def get_dynamic(row):
    """
    Find dynamic definitions on a row
    """

    prop_dict = AppendingDict()
    try:
        formula = row["formula"].strip()
        if "type" in row:
            # TODO: Sanity check type?
            formula = "%s(%s)" % (row["type"], formula)
        check_formula(formula)
        mode = str(row["mode"])
        if mode.lower() == "status":
            dyn = formula
        else:
            dyn = "%s=%s" % (row["name"], formula)
        prop_dict[MODE_MAPPING[mode]] = dyn
    except KeyError as e:
        raise ValueError("Problem with formula: %s" % e)

    return prop_dict


def make_db_name(name):
    """
    Convert a Space Separated Name into a lowercase, underscore_separated_name
    """
    return name.strip().lower().replace(" ", "_")


def check_formula(formula):
    """
    Syntax check a dynamic formula.
    """
    compile(formula, "<stdin>", "single")


def check_device_format(devname):
    """
    Verify that a device name is of the correct form (three parts
    separated by slashes, only letters, numbers, dashes and
    underscores allowed.)  Note: We could put more logic here to make
    device names conform to a standard.
    """
    device_pattern = "^[\w-]+/[\w-]+/[\w-]+$"
    if not re.match(device_pattern, devname):
        raise ValueError("device name '%s' not valid" % devname)


def format_server_instance(row):
    """
    Format a server/instance string
    """
    # TODO: handle numeric instance names? They tend to turn up as floats...
    return "%s/%s" % (row["server"], row["instance"])


def convert(rows, definitions, skip=True, dynamic=False, config=False):
    """
    Update a dict of definitions from data
    """

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
                                    for name, col in zip(column_names, row_)
                                    if col not in ("", None)))

            # Skip empty lines
            if not row:
                continue

            # Target of the properties; device or class?
            if "device" in row:
                check_device_format(row["device"])
                if "server" in row:
                    # full device definition
                    # target is "lazily" evaluated, so that we don't create
                    # an empty dict if it turns out there are no members
                    target = lambda: definitions.servers[row["server"]][row["instance"]] \
                        [row["class"]][row["device"]]
                else:
                    # don't know if the device is already defined
                    target = lambda: find_device(definitions, row["device"])[0]
            elif "class" in row:
                # class definition
                target = lambda: definitions.classes[row["class"]]
            else:
                continue

            if dynamic:
                props = get_dynamic(row)
                if props:
                    target().properties = props

            elif config:
                attr_props = get_attribute_properties(row)
                if attr_props:
                    target().attribute_properties = attr_props
            else:
                props = get_properties(row)
                if props:
                    target().properties = props

        except KeyError as ke:
            # handle_error(i, "insufficient data (%s)" % ke)
            pass
        except ValueError as ve:
            handle_error(i, "Error: %s" % ve)
        except SyntaxError as se:
            # TODO: do something here to show more info about the error
            # ex_type, ex, tb = sys.exc_info()
            # "\n".join(format_exc(ex).splitlines()[-3:]
            handle_error(i, "SyntaxError: %s" % se)

    return errors


def print_errors(errors):
    if errors:
        print("%d lines skipped" % len(errors), file=sys.stderr)
        for err in errors:
            line, msg = err
            print("%d: %s" % (line + 1, msg), file=sys.stderr)


def xls_to_dict(xls_filename, pages=None, skip=False):
    """
    Make JSON out of an XLS sheet of device definitions.
    """

    import xlrd

    xls = xlrd.open_workbook(xls_filename)
    definitions = AppendingDict()

    if not pages:  # if no pages given, assume all pages are wanted
        pages = xls.sheet_names()
    else:
        # Always include Dynamics and ParamConfig as they only add stuff
        # to devices already configured anyway.
        if "Dynamics" not in pages and "Dynamics" in xls.sheet_names():
            pages.append("Dynamics")
        if "ParamConfig" not in pages and "ParamConfig" in xls.sheet_names():
            pages.append("ParamConfig")

    for page in pages:

        print("\nPage: %s" % page, file=sys.stderr)
        sheet = xls.sheet_by_name(page)
        rows = [sheet.row_values(i)
                for i in range(sheet.nrows)]
        if not rows:
            continue  # ignore empty pages
        errors = convert(rows, definitions, skip=skip,
                         dynamic=(page == "Dynamics"),
                         config=(page == "ParamConfig"))
        print_errors(errors)

    return definitions


def get_stats(defs):
    """
    Calculate some numbers
    """

    servers = set()
    instances = set()
    classes = set()
    devices = set()

    for server, instances in list(defs.servers.items()):
        servers.add(server)
        instances.update(instances)
        for clsname, devs in list(instances.items()):
            classes.add(clsname)
            for devname, dev in list(devs.items()):
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
        print(json.dumps(data, indent=4))
        outfile = open('config.json', 'w')
        json.dump(data, outfile, indent=4)

    stats = get_stats(data)

    print(("\n"
           "Total: %(servers)d servers, %(instances)d instances, "
           "%(classes)d classes and %(devices)d devices defined.") % stats, file=sys.stderr)


if __name__ == "__main__":
    main()
