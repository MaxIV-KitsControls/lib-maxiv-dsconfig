"This module concerns the dsconfig JSON file format"

import sys
import json
from copy import deepcopy
from os import path

from appending_dict import AppendingDict

import PyTango


SERVERS_LEVELS = {"server": 0, "instance": 1, "class": 2, "device": 3, "property": 5}
CLASSES_LEVELS = {"class": 1, "property": 2}

module_path = path.dirname(path.realpath(__file__))
SCHEMA_FILENAME = path.join(module_path, "schema/schema2.json")  #rename


# functions to decode unicode JSON (PyTango does not like unicode strings)

def decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = str(item.encode('utf-8'))
        elif isinstance(item, list):
            item = decode_list(item)
        elif isinstance(item, dict):
            item = decode_dict(item)
        rv.append(item)
    return rv


def decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = str(key.encode('utf-8'))
        if isinstance(value, unicode):
            value = str(value.encode('utf-8'))
        elif isinstance(value, list):
            value = decode_list(value)
        elif isinstance(value, dict):
            value = decode_dict(value)
        rv[key] = value
    return rv


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


def load_json(f):
    return json.load(f, object_hook=decode_dict)


def expand_config(config):

    """Takes a configuration dict and expands it into the canonical
    format. This currently means that the server instance level is
    split into a server and an instance level."""

    expanded = deepcopy(config)
    for servername in config["servers"]:
        if "/" in servername:
            server, instance = servername.split("/")
            data = expanded["servers"].pop(servername)
            if server in expanded["servers"]:
                expanded["servers"][server].update({instance: data})
            else:
                expanded["servers"][server] = {instance: data}
    return expanded


def normalize_config(config):

    """Take a 'loose' config and return a new config that conforms to the
    DSConfig format.

    Current transforms:

    - server instances (e.g. 'TangoTest/1') are split into a server
      level and an instance level (e.g. 'TangoTest' -> '1'). This is to
      convert "v1" format files to the "v2" format.

    - "devices" toplevel; allows to change *existing* devices by just
      adding them directly to a "devices" key in the config, instead
      of having to list out the server, instance and class (since this
      information can be gotten from the DB.)

    """
    old_config = expand_config(config)
    new_config = AppendingDict()
    if "servers" in old_config:
        new_config.servers = old_config["servers"]
    if "classes" in old_config:
        new_config.classes = old_config["classes"]
    if "devices" in old_config:
        db = PyTango.Database()
        for device, props in old_config["devices"].items():
            try:
                info = db.get_device_info(device)
            except PyTango.DevFailed as e:
                sys.exit("Can't reconfigure device %s: %s" % (device, str(e[0].desc)))
            srv, inst = info.ds_full_name.split("/")
            new_config.servers[srv][inst][info.class_name][device] = props

    return new_config.to_dict()
