import re

from .appending_dict import merge


def filter_nested_dict(node, pattern, depth, level=0, invert=False):
    """
    Filter the parts of a nested dict where keys match regex pattern,
    at the given depth.
    """
    if level == depth:
        return dict((key, value) for key, value in node.items()
                    if (not invert and pattern.match(key)) or
                    (invert and not pattern.match(key)))
    else:
        dupe_node = {}
        for key, val in node.items():
            cur_node = filter_nested_dict(val, pattern, depth, level+1,
                                          invert)
            if cur_node:
                dupe_node[key] = cur_node
        return dupe_node or None


def filter_config(data, filters, levels, invert=False):

    """Filter the given config data according to a list of filters.
    May be a positive filter (i.e. includes only matching things)
    or inverted (i.e. includes everything that does not match).
    The _levels_ argument is used to find at what depth in the data
    the filtering should happen.
    """

    filtered = data if invert else {}
    for fltr in filters:
        try:
            what, regex = fltr.split(":")
            if what == "server" and "/" in regex:
                # special case the "server/instance" syntax to return
                # only the specific instance in the server
                srv, inst = [re.compile(r, flags=re.IGNORECASE)
                             for r in regex.split("/")]
                servers = filter_nested_dict(data, srv, 0)
                for k, v in list(servers.items()):
                    tmp = filter_nested_dict(v, inst, 0)
                    if tmp:
                        filtered[k] = tmp
                continue
            depth = levels[what]
            pattern = re.compile(regex, flags=re.IGNORECASE)
        except (ValueError, IndexError):
            raise ValueError(
                "Bad filter '%s'; should be '<term>:<regex>'" % fltr)
        except KeyError:
            raise ValueError("Bad filter '%s'; term should be one of: %s"
                             % (fltr, ", ".join(list(levels.keys()))))
        except re.error as e:
            raise ValueError("Bad regular expression '%s': %s" % (fltr, e))
        if invert:
            filtered = filter_nested_dict(filtered, pattern, depth,
                                          invert=True)
        else:
            tmp = filter_nested_dict(data, pattern, depth)
            if tmp:
                merge(filtered, tmp)
    return filtered
