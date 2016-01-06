"""
These tests use the 'faker' module to randomly generate
configurations.  It's intended to be run many times in succession in
order to find corner cases.

It does not use a real TANGO database.
"""

from copy import deepcopy
from random import choice, randint

from faker import Faker
import PyTango

from dsconfig.configure import configure
from providers import TangoProvider


fake = Faker()
fake.add_provider(TangoProvider)


# # # #  HELPERS  # # # #

def pick_random_server(config):
    server = choice(config["servers"].keys())
    return server, config["servers"][server]


def pick_random_instance(config):
    servername, instances = pick_random_server(config)
    instance = choice(instances.keys())
    return servername, instance, instances[instance]


def pick_random_class(config):
    servername, instname, classes = pick_random_instance(config)
    classname = choice(classes.keys())
    return servername, instname, classname, classes[classname]


def pick_random_device(config):
    srv, inst, clss, devices = pick_random_class(config)
    devname = choice(devices.keys())
    return srv, inst, clss, devname, devices[devname]


def pick_random_property(config):
    srv, inst, clss, dev, properties = pick_random_device(config)
    propname = choice(properties["properties"].keys())
    return srv, inst, clss, dev, propname, properties["properties"][propname]


def pick_random_class_property(config):
    classes = config["classes"]
    classname = choice(classes.keys())
    properties = classes[classname]
    propname = choice(properties["properties"].keys())
    return classname, propname, properties["properties"][propname]


# # # #  TESTS  # # # #

# === Device Properties ===

def test_modify_device_property_line():

    """Check that a property is updated when a line is changed"""

    config = fake.tango_database()
    orig_config = deepcopy(config)
    srv, inst, clss, dev, name, value = pick_random_property(config)
    value[randint(0, len(value)-1)] = fake.word()
    calls = configure(config, orig_config)

    assert len(calls) == 1
    expected = ("put_device_property", (dev, {name: value}), {})
    assert calls[0] == expected


def test_remove_device_property_line():

    """Check that the property is overwritten with the new value when
    removing a line from a property"""

    config = fake.tango_database()
    orig_config = deepcopy(config)
    _, _, _, dev, name, value = pick_random_property(config)
    del value[randint(0, len(value)-1)]
    calls = configure(config, orig_config)

    assert len(calls) == 1
    expected = ("put_device_property", (dev, {name: value}), {})
    assert calls[0] == expected


def test_remove_device_property():

    """Check that the property is removed"""

    config = fake.tango_database()
    orig_config = deepcopy(config)
    srv, inst, clss, dev, name, value = pick_random_property(config)
    del config["servers"][srv][inst][clss][dev]["properties"][name]
    calls = configure(config, orig_config)

    assert len(calls) == 1
    expected = ("delete_device_property", (dev, {name: value}), {})
    assert calls[0] == expected


def test_add_device_property():

    "Check that the property is added"

    config = fake.tango_database()
    orig_config = deepcopy(config)

    name, value = fake.tango_property()
    _, _, _, dev, props = pick_random_device(config)
    props["properties"][name] = value
    calls = configure(config, orig_config)

    assert len(calls) == 1
    expected = ("put_device_property", (dev, {name: value}), {})
    assert calls[0] == expected


# === Class properties ===

def test_modify_class_property_line():

    """Check that a property is updated when a line is changed"""

    config = fake.tango_database(classes=(3, 5))
    orig_config = deepcopy(config)

    clss, name, value = pick_random_class_property(config)
    value[randint(0, len(value)-1)] = fake.word()
    calls = configure(config, orig_config)

    assert len(calls) == 1
    expected = ("put_class_property", (clss, {name: value}), {})
    assert calls[0] == expected


def test_remove_class_property_line():

    """Check that the property is overwritten with the new value when
    removing a line from a property"""

    config = fake.tango_database(classes=(3, 5))
    orig_config = deepcopy(config)
    clss, name, value = pick_random_class_property(config)
    del value[randint(0, len(value)-1)]
    calls = configure(config, orig_config)

    assert len(calls) == 1
    expected = ("put_class_property", (clss, {name: value}), {})
    assert calls[0] == expected


def test_remove_class_property():

    """Check that the property is removed"""

    config = fake.tango_database(classes=(3, 5))
    orig_config = deepcopy(config)
    clss, name, value = pick_random_class_property(config)
    del config["classes"][clss]["properties"][name]
    calls = configure(config, orig_config)

    assert len(calls) == 1
    expected = ("delete_class_property", (clss, {name: value}), {})
    assert calls[0] == expected


def test_add_class_property():

    "Check that the property is added"

    config = fake.tango_database(classes=(3, 5))
    orig_config = deepcopy(config)

    name, value = fake.tango_property()
    clss = choice(config["classes"].keys())
    props = config["classes"][clss]
    props["properties"][name] = value
    calls = configure(config, orig_config)

    assert len(calls) == 1
    expected = ("put_class_property", (clss, {name: value}), {})
    assert calls[0] == expected


# === Device attribute properties ===

def test_add_attribute_property():

    "Check that the attribute property is added"

    config = fake.tango_database()
    orig_config = deepcopy(config)

    _, _, _, dev, props = pick_random_device(config)
    attr = "test_attribute"
    propname, value = fake.tango_attribute_property()
    if "attribute_properties" not in props:
        props["attribute_properties"] = {}
    props["attribute_properties"][attr] = {propname: value}
    calls = configure(config, orig_config)

    assert len(calls) == 1
    expected = ("put_device_attribute_property",
                (dev, {attr: {propname: value}}), {})
    assert calls[0] == expected


def test_modify_attribute_property():

    "Check that the attribute property is changed"

    config = fake.tango_database()

    _, _, _, dev, props = pick_random_device(config)
    attr = "test_attribute"
    propname, value = fake.tango_attribute_property()
    if "attribute_properties" not in props:
        props["attribute_properties"] = {}
    props["attribute_properties"][attr] = {propname: value}
    orig_config = deepcopy(config)
    props["attribute_properties"][attr][propname] = "abc"
    calls = configure(config, orig_config)

    assert len(calls) == 1
    expected = ("put_device_attribute_property",
                (dev, {attr: {propname: "abc"}}), {})
    assert calls[0] == expected


def test_cant_remove_protected_attribute_property():

    "Check that the attribute property is *not* removed"

    config = fake.tango_database()

    _, _, _, dev, props = pick_random_device(config)
    attr = "test_attribute"
    propname, value = fake.tango_attribute_property()
    if "attribute_properties" not in props:
        props["attribute_properties"] = {}
    props["attribute_properties"][attr] = {propname: value}
    orig_config = deepcopy(config)
    del props["attribute_properties"][attr][propname]
    calls = configure(config, orig_config)

    assert len(calls) == 0


# === Class attribute properties ===

def test_add_class_attribute_property():

    "Check that the attribute property is added"

    config = fake.tango_database(classes=(3, 5))
    orig_config = deepcopy(config)

    clss = choice(config["classes"].keys())
    props = config["classes"][clss]
    attr = "test_attribute"
    propname, value = fake.tango_attribute_property()
    if "attribute_properties" not in props:
        props["attribute_properties"] = {}
    props["attribute_properties"][attr] = {propname: value}
    calls = configure(config, orig_config)

    assert len(calls) == 1
    expected = ("put_class_attribute_property",
                (clss, {attr: {propname: value}}), {})
    assert calls[0] == expected


def test_modify_class_attribute_property():

    "Check that the attribute property is changed"

    config = fake.tango_database()

    clss = choice(config["classes"].keys())
    props = config["classes"][clss]
    attr = "test_attribute"
    propname, value = fake.tango_attribute_property()
    if "attribute_properties" not in props:
        props["attribute_properties"] = {}
    props["attribute_properties"][attr] = {propname: value}
    orig_config = deepcopy(config)
    props["attribute_properties"][attr][propname] = "abc"
    calls = configure(config, orig_config)

    assert len(calls) == 1
    expected = ("put_class_attribute_property",
                (clss, {attr: {propname: "abc"}}), {})
    assert calls[0] == expected


def test_cant_remove_protected_class_attribute_property():

    "Check that the attribute property is *not* removed"

    config = fake.tango_database()

    clss = choice(config["classes"].keys())
    props = config["classes"][clss]
    attr = "test_attribute"
    propname, value = fake.tango_attribute_property()
    if "attribute_properties" not in props:
        props["attribute_properties"] = {}
    props["attribute_properties"][attr] = {propname: value}
    orig_config = deepcopy(config)
    del props["attribute_properties"][attr][propname]
    calls = configure(config, orig_config)

    assert len(calls) == 0


# === Device operations ===

def test_add_device_to_existing_class():

    config = fake.tango_database()
    orig_config = deepcopy(config)

    srv, inst, cls, devices = pick_random_class(config)
    devname, device = fake.tango_device()
    devices[devname] = {}
    calls = configure(config, orig_config)

    assert len(calls) == 1
    method, [info], kwargs = calls[0]
    assert method == "add_device"
    assert type(info) == PyTango.DbDevInfo
    assert info.server == "%s/%s" % (srv, inst)
    assert info.klass == cls
    assert info.name == devname


def test_add_device_to_existing_instance():

    config = fake.tango_database()
    orig_config = deepcopy(config)

    srv, inst, classes = pick_random_instance(config)
    classname, _ = fake.tango_class()
    devname, device = fake.tango_device()
    classes[classname] = {devname: {}}
    calls = configure(config, orig_config)

    assert len(calls) == 1
    method, [info], kwargs = calls[0]
    assert method == "add_device"
    assert type(info) == PyTango.DbDevInfo
    assert info.server == "%s/%s" % (srv, inst)
    assert info.klass == classname
    assert info.name == devname


def test_add_device_to_existing_server():

    config = fake.tango_database()
    orig_config = deepcopy(config)

    srv, instances = pick_random_server(config)
    instname, _ = fake.tango_instance()
    classname, _ = fake.tango_class()
    devname, device = fake.tango_device()
    instances[instname] = {classname: {devname: {}}}
    calls = configure(config, orig_config)

    assert len(calls) == 1
    method, [info], kwargs = calls[0]
    assert method == "add_device"
    assert type(info) == PyTango.DbDevInfo
    assert info.server == "%s/%s" % (srv, instname)
    assert info.klass == classname
    assert info.name == devname


def test_remove_device():

    config = fake.tango_database()
    orig_config = deepcopy(config)

    _, _, classname, devices = pick_random_class(config)
    device = choice(devices.keys())
    del devices[device]
    calls = configure(config, orig_config)

    assert len(calls) == 1
    assert calls[0] == ("delete_device", (device,), {})


# === Server operations ===

def test_add_server():

    config = fake.tango_database()
    orig_config = deepcopy(config)

    config["servers"]["test_server"] = {
        "test_instance": {
            "test_class": {
                "my/test/device": {}
            }
        }
    }
    calls = configure(config, orig_config)

    assert len(calls) == 1
    method, [info], kwargs = calls[0]
    assert method == "add_device"
    assert type(info) == PyTango.DbDevInfo
    assert info.server == "test_server/test_instance"
    assert info.klass == "test_class"
    assert info.name == "my/test/device"
