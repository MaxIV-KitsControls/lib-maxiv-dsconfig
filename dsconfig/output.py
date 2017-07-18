from difflib import ndiff

from PyTango.utils import CaselessDict

from dsconfig.utils import green, red, yellow
from dsconfig.tangodb import get_devices_from_dict
from appending_dict import SetterDict


def get_device_data(device, mapping, data):
    if device in mapping:
        server, instance, clss = mapping[device]
        return CaselessDict(data["servers"][server][instance][clss]).get(device, {})
    return {}


def property_diff(old, new, indentation=""):
    diff = ndiff(old, new)
    lines = []
    for line in diff:
        if line.startswith("+"):
            lines.append(green("{}{}".format(indentation, line)))
        elif line.startswith("-"):
            lines.append(red("{}{}".format(indentation, line)))
        else:
            lines.append("{}{}".format(indentation, line))
    return "\n".join(lines)


def format_property(value, indentation="", max_lines=10):
    if len(value) > max_lines:
        ending = "\n{}... [{} lines]".format(indentation, len(value) - max_lines)
    else:
        ending = ""
    return "\n".join("{}{}".format(indentation, line)
                     for line in value[:max_lines]) + ending


def get_changes(data, calls):

    """Combine a list of database calls into "changes" that can
    be more easily turned into a readable representation"""

    devices = get_devices_from_dict(data["servers"])
    device_mapping = CaselessDict(
        (device, (server, instance, clss))
        for server, instance, clss, device in devices
    )
    classes = data.get("classes", {})

    # The idea is to first go through all database calls and collect
    # the changes per device. Then we can print it all out in a more
    # readable format since it will all be collected per device.
    #
    # Example of resulting dict:
    # {
    #     "sys/tg_test/1": {
    #         "server": "TangoTest",
    #         "instance": "test",
    #         "device_class": "TangoTest",
    #         "properties": {
    #             # added property has no old_value
    #             "hej": {
    #                 "value": ["a", "b", "c"]
    #             },
    #             # removed property has no value
    #             "svej": {
    #                 "old_value": ["dsaodkasokd"]
    #             },
    #             # changed property has both
    #             "flepp": {
    #                 "old_value": ["1", "3"],
    #                 "value": ["1", "2", "3"]
    #             }
    #         }
    #     }
    # }

    changes = {
        "devices": SetterDict(),
        "classes": SetterDict()
    }

    # Go through all database calls and store the changes
    for method, args, kwargs in calls:

        if method == "put_device_alias":
            device, alias = args
            if device in device_mapping:
                old_alias = get_device_data(
                    device, device_mapping, data).get("alias")
            else:
                old_alias = None
            changes["devices"][device].update({
                "alias": {"old_value": old_alias,
                          "value": alias}
            })

        elif method == "add_device":
            info, = args
            changes["devices"][info.name].update(added=True,
                                                 server=info.server,
                                                 device_class=info._class)
            if info.name in device_mapping:
                old_server, old_instance, old_class = device_mapping[info.name]
                changes["devices"][info.name]["old_server"] = "{}/{}".format(
                    old_server, old_instance)
                changes["devices"][info.name]["old_class"] = old_class

        elif method == "delete_device":
            device, = args
            server, instance, clss = device_mapping[device]
            device_data = data["servers"][server][instance][clss]
            properties = device_data.get("properties", {})
            changes["devices"][device].update(
                deleted=True,
                server="{}/{}".format(server, instance),
                instance=instance,
                device_class=clss,
                properties=properties)

        elif method == "put_device_property":
            device, properties = args
            old_data = get_device_data(device, device_mapping, data)
            caseless_props = CaselessDict(old_data.get("properties", {}))
            if "properties" not in changes["devices"][device]:
                changes["devices"][device]["properties"] = {}
            for name, value in properties.items():
                old_value = caseless_props.get(name)
                if value != old_value:
                    changes["devices"][device]["properties"].update({
                        name: {
                            "value": value,
                            "old_value": old_value
                        }
                    })

        elif method == "delete_device_property":
            device, properties = args
            old_data = get_device_data(device, device_mapping, data)
            caseless_props = CaselessDict(old_data.get("properties", {}))
            prop_changes = changes["devices"][device].setdefault(
                "properties", {})
            for prop in properties:
                old_value = caseless_props[prop]
                prop_changes[prop] = {"old_value": old_value}

        elif method == "put_device_attribute_property":
            device, properties = args
            attr_props = changes["devices"][device].setdefault(
                "attribute_properties", {})
            old_data = get_device_data(device, device_mapping, data)
            caseless_attrs = CaselessDict(old_data.get(
                "attribute_properties", {}))
            for attr, props in properties.items():
                caseless_props = CaselessDict(caseless_attrs.get(attr, {}))
                for name, value in props.items():
                    old_value = caseless_props.get(name)
                    if value != old_value:
                        attr_props[attr] = {
                            name: {"old_value": old_value,
                                   "value": value}
                        }

        elif method == "delete_device_attribute_property":
            device, attributes = args
            prop_changes = attr_props = changes["devices"][device].setdefault(
                "attribute_properties", {})
            old_data = get_device_data(device, device_mapping, data)
            caseless_attrs = CaselessDict(old_data.get("attribute_properties", {}))
            for attr, props in attributes.items():
                caseless_props = CaselessDict(caseless_attrs[attr])
                for prop in props:
                    old_value = caseless_props.get(prop)
                    attr_props[attr] = {prop: {"old_value": old_value}}

        elif method == "put_class_property":
            clss, properties = args
            old_data = classes[clss]
            caseless_props = CaselessDict(old_data.get("properties", {}))
            prop_changes = changes["classes"][clss].setdefault("properties", {})
            for name, value in properties.items():
                old_value = caseless_props.get(name)
                if value != old_value:
                    prop_changes.update({
                        name: {
                            "value": value,
                            "old_value": old_value}
                    })

        elif method == "delete_class_property":
            clss, properties = args
            old_data = classes[clss]
            caseless_props = CaselessDict(old_data.get("properties", {}))
            prop_changes = changes["classes"][clss].setdefault("properties", {})
            for prop in properties:
                old_value = caseless_props[prop]
                prop_changes[prop] = {"old_value": old_value}

        elif method == "put_class_attribute_property":
            clss, properties = args
            attr_props = changes["classes"][clss].setdefault(
                "attribute_properties", {})
            old_data = classes[clss]
            caseless_attrs = CaselessDict(
                old_data.get("attribute_properties", {}))
            for attr, props in properties.items():
                caseless_props = CaselessDict(caseless_attrs.get(attr, {}))
                for name, value in props.items():
                    old_value = caseless_props.get(name)
                    if value != old_value:
                        attr_props[attr] = {
                            name: {"old_value": old_value,
                                   "value": value}
                        }

        elif method == "delete_class_attribute_property":
            clss, attributes = args
            attr_props = changes["classes"][clss].setdefault(
                "attribute_properties", {})
            old_data = classes[clss]
            caseless_attrs = CaselessDict(old_data.get("properties", {}))
            for attr, props in attributes.items():
                caseless_props = CaselessDict(caseless_attrs[attr])
                for prop in props:
                    old_value = caseless_props.get(prop)
                    attr_props[attr] = {prop: {"old_value": old_value}}

    return {
        "devices": changes["devices"].to_dict(),
        "classes": changes["classes"].to_dict(),
    }


def show_actions(data, calls):

    "Print out a human readable representation of changes"

    changes = get_changes(data, calls)

    # Go through all the devices that have been touched
    # and print out a representation of the changes.
    # TODO: is there a more reasonable way to sort this?
    indent = " " * 2
    for device in sorted(changes["devices"]):
        info = changes["devices"][device]
        if info.get("added"):
            if info.get("old_server"):
                print("{} Device: {}".format(yellow("="), device))
            else:
                print("{} Device: {}".format(green("+"), device))
        elif info.get("deleted"):
            print("{} Device: {}".format(red("-"), device))
        else:
            print("{} Device: {}".format(yellow("="), device))

        if info.get("server"):
            if info.get("old_server"):
                print("{}Server: {} -> {}".format(indent,
                                                  red(info["old_server"]),
                                                  green(info["server"])))
            else:
                print("{}Server: {}".format(indent, info["server"]))

        if info.get("device_class"):
            if info.get("old_class"):
                if info["old_class"] != info["device_class"]:
                    print("{}Class: {} -> {}".format(indent,
                                                     info["old_class"],
                                                     info["device_class"]))
            else:
                print("{}Class: {}".format(indent, info["device_class"]))

        if info.get("alias"):
            alias = info.get("alias").get("value")
            old_alias = info.get("alias").get("old_value")
            if old_alias:
                if old_alias != alias:
                    print("{}Alias: {} -> {}".format(indent, red(old_alias),
                                                     green(alias)))
            else:
                print("{}Alias: {}".format(indent, alias))

        if info.get("properties"):
            lines = []
            for prop, change in sorted(info.get("properties", {}).items()):
                if change.get("value"):
                    value = change.get("value")
                    old_value = change.get("old_value")
                    if old_value is not None:
                        if old_value != value:
                            # change property
                            lines.append(yellow("{}= {}".format(indent*2, prop)))
                            lines.append(property_diff(
                                change["old_value"], change["value"], indent*3))
                    else:
                        # new property
                        lines.append(green("{}+ {}".format(indent*2, prop)))
                        lines.append(green(format_property(change["value"],
                                                           indent*3)))
                else:
                    # delete property
                    lines.append(red("{}- {}".format(indent*2, prop)))
                    lines.append(red(format_property(change["old_value"], indent*3)))
            if lines:
                print("{}Properties:".format(indent*1))
                print("\n".join(lines))

        if info.get("attribute_properties"):
            lines = []
            for attr, props in sorted(
                    info.get("attribute_properties", {}).items()):
                attr_lines = []
                for prop, change in sorted(props.items()):
                    value = change.get("value")
                    old_value = change.get("old_value")
                    if value is not None:
                        if old_value is not None:
                            # change
                            if value != old_value:
                                attr_lines.append(yellow("{}= {}".format(indent*3, prop)))
                                attr_lines.append(property_diff(
                                    change["old_value"], change["value"], indent*4))
                        else:
                            # addition
                            attr_lines.append(green("{}+ {}".format(indent*3, prop)))
                            attr_lines.append(green(format_property(change["value"],
                                                                    indent*4)))
                    else:
                        # removal
                        attr_lines.append(red("{}- {}".format(indent*3, prop)))
                        attr_lines.append(red(format_property(change["old_value"],
                                                              indent*4)))
                if attr_lines:
                    lines.append("{}{}".format(indent*2, attr))
                    lines.extend(attr_lines)
            if lines:
                print("{}Attribute properties:".format(indent))
                print("\n".join(lines))
        print
