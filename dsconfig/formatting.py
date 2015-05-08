"This module concerns the dsconfig JSON file format"

import json
from os import path
import sys

import PyTango

from appending_dict import AppendingDict


SERVERS_LEVELS = {"server": 0, "class": 1, "device": 2, "property": 4}
CLASSES_LEVELS = {"class": 1, "property": 2}

module_path = path.dirname(path.realpath(__file__))
SCHEMA_FILENAME = path.join(module_path, "schema/dsconfig.json")


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


def normalize_config(config):

    """Take a 'loose' config and return a new config that conforms to the
    DSConfig format.

    Current transforms:
    - "devices" toplevel; allows to change *existing* devices by just adding
      them directly to a "devices" key in the config, instead of having to
      list out the server, instance and class (since this information can be
      gotten from the DB.)

    """

    new_config = AppendingDict()
    if "servers" in config:
        new_config.servers = config["servers"]
    if "classes" in config:
        new_config.classes = config["classes"]
    if "devices" in config:
        db = PyTango.Database()
        for device, props in config["devices"].items():
            try:
                info = db.get_device_info(device)
            except PyTango.DevFailed as e:
                sys.exit("Can't reconfigure device %s: %s" % (device, str(e[0].desc)))
            new_config.servers[info.ds_full_name][info.class_name][device] = props

    return new_config.to_dict()
