from collections import Mapping
import json
import sys

from .utils import green, yellow, red


def decode_pointer(ptr):
    """Take a string representing a JSON pointer and return a
    sequence of parts, decoded."""
    return [p.replace("~1", "/").replace("~0", "~")
            for p in ptr.split("/")]


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
                    print(yellow("REPLACE:"))
                    print(yellow(ptr))
                    db_value = resolve_pointer(dbdict, d["path"])
                    print(red(dump_value(db_value)))
                    print(green(dump_value(d["value"])))
                    ops["replace"] += 1
                if d["op"] == "add":
                    print(green("ADD:"))
                    print(green(ptr))
                    if d["value"]:
                        print(green(dump_value(d["value"])))
                    ops["add"] += 1
                if removes and d["op"] == "remove":
                    print(red("REMOVE:"))
                    print(red(ptr))
                    value = resolve_pointer(dbdict, d["path"])
                    if value:
                        print(red(dump_value(value)))
                    ops["remove"] += 1
            except JsonPointerException as e:
                print(" - Error parsing diff - report this!: %s" % e)
        # # The following output is a bit misleading, removing for now
        # print "Total: %d operations (%d replace, %d add, %d remove)" % (
        #     sum(ops.values()), ops["replace"], ops["add"], ops["remove"])
        return diff
    except ImportError:
        print(("'jsonpatch' module not available - "
                             "no diff printouts for you! (Try -d instead.)"), file=sys.stderr)


