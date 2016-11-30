from collections import defaultdict
from difflib import ndiff

from PyTango.utils import CaselessDict

from dsconfig.utils import green, red, yellow
from dsconfig.tangodb import get_devices_from_dict


def get_device_data(device, mapping, data):
    if device in mapping:
        server, instance, clss = mapping[device]
        return CaselessDict(data["servers"][server][instance][clss]).get(device, {})
    return {}


def print_property_diff(old, new, indentation=""):
    diff = ndiff(old, new)
    for line in diff:
        if line.startswith("+"):
            print(green("{}{}".format(indentation, line)))
        elif line.startswith("-"):
            print(red("{}{}".format(indentation, line)))
        else:
            print("{}{}".format(indentation, line))


def format_property(value, indentation="", max_lines=10):
    if len(value) > max_lines:
        ending = "\n{}... [{} lines]".format(indentation, len(value) - max_lines)
    else:
        ending = ""
    return "\n".join("{}{}".format(indentation, line)
                     for line in value[:max_lines]) + ending


def show_actions(data, calls):

    """Print out a human readable list of what changes would be made
    to the database given the database state and a list of calls"""

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
        "devices": defaultdict(dict),
        "classes": defaultdict(dict)
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

        elif method == "delete_device":
            device, = args
            server, instance, clss = device_mapping[device]
            device_data = data["servers"][server][instance][clss]
            properties = device_data.get("properties", {})
            changes["devices"][device].update(
                deleted=True,
                server=server,
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
                changes["devices"][device]["properties"].update({
                    name: {
                        "value": value,
                        "old_value": old_value}
                })

        elif method == "delete_device_property":
            device, properties = args
            old_data = get_device_data(device, device_mapping, data)
            caseless_props = CaselessDict(old_data.get("properties", {}))
            prop_changes = changes["devices"][device].setdefault("properties", {})
            for prop in properties:
                old_value = caseless_props[prop]
                prop_changes[prop] = {"old_value": old_value}

        elif method == "put_device_attribute_property":
            device, properties = args
            attr_props = changes["devices"][device].setdefault("attribute_properties", {})
            old_data = get_device_data(device, device_mapping, data)
            caseless_attrs = CaselessDict(old_data.get("attribute_properties", {}))
            for attr, props in properties.items():
                caseless_props = CaselessDict(caseless_attrs.get(attr, {}))
                for name, value in props.items():
                    old_value = caseless_props.get(name)
                    attr_props[attr] = {
                        name: {"old_value": old_value,
                               "value": value}
                    }

        elif method == "delete_device_attribute_property":
            device, attributes = args
            prop_changes = attr_props = changes["devices"][device].setdefault("attribute_properties", {})
            old_data = get_device_data(device, device_mapping, data)
            caseless_attrs = CaselessDict(old_data.get("properties", {}))
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
            attr_props = changes["classes"][clss].setdefault("attribute_properties", {})
            old_data = classes[clss]
            caseless_attrs = CaselessDict(old_data.get("attribute_properties", {}))
            for attr, props in properties.items():
                caseless_props = CaselessDict(caseless_attrs.get(attr, {}))
                for name, value in props.items():
                    old_value = caseless_props.get(name)
                    attr_props[attr] = {
                        name: {"old_value": old_value,
                               "value": value}
                    }

        elif method == "delete_class_attribute_property":
            clss, attributes = args
            attr_props = changes["classes"][clss].setdefault("attribute_properties", {})
            old_data = classes[clss]
            caseless_attrs = CaselessDict(old_data.get("properties", {}))
            for attr, props in attributes.items():
                caseless_props = CaselessDict(caseless_attrs[attr])
                for prop in props:
                    old_value = caseless_props.get(prop)
                    attr_props[attr] = {prop: {"old_value": old_value}}

    # Now we go through all the devices that have been touched
    # and print out a representation of the changes.
    indent = " " * 4
    for device in sorted(changes["devices"]):
        info = changes["devices"][device]
        if info.get("added"):
            print("{} {}".format(green("ADD"), device))
        elif info.get("deleted"):
            print("{} {}".format(red("DEL"), device))
        else:
            print(device)
        if info.get("server"):
            print("{}Server: {}".format(indent, info["server"]))
        if info.get("device_class"):
            print("{}Class: {}".format(indent, info["device_class"]))
        if info.get("alias"):
            print("{}{}".format(indent, "Alias:"))
            alias = info.get("alias").get("value")
            old_alias = info.get("alias").get("old_value")
            if old_alias:
                print("{}-{}".format(indent*2, red(old_alias)))
            print("{}+ {}".format(indent*2, green(alias)))
        if info.get("properties"):
            print("{}Properties:".format(indent*1))
            for prop, change in sorted(info.get("properties", {}).items()):
                if change.get("value"):
                    if change.get("old_value"):
                        print(yellow("{}= {}".format(indent*2, prop)))
                        print_property_diff(
                            change["old_value"], change["value"], indent*3)
                    else:
                        print(green("{}+ {}".format(indent*2, prop)))
                        print(green(format_property(change["value"], indent*3)))
                else:
                    print(red("{}- {}".format(indent*2, prop)))
                    print(red(format_property(change["old_value"], indent*3)))
        if info.get("attribute_properties"):
            print("{}Attribute properties:".format(indent))
            for attr, props in sorted(info.get("attribute_properties", {}).items()):
                print("{}{}".format(indent*2, attr))
                for prop, change in sorted(props.items()):
                    if change.get("value"):
                        if change.get("old_value"):
                            # change
                            print(yellow("{}= {}".format(indent*3, prop)))
                            print_property_diff(
                                change["old_value"], change["value"], indent*4)
                        else:
                            # addition
                            print(green("{}+ {}".format(indent*3, prop)))
                            print(green(format_property(change["value"], indent*4)))
                    else:
                        # removal
                        print(red("{}- {}".format(indent*3, prop)))
                        print(red(format_property(change["old_value"], indent*4)))
