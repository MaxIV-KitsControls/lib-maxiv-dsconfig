from functools import partial

from appending_dict import AppendingDict

#colors
ADD = GREEN = '\033[92m'
REMOVE = RED = FAIL = '\033[91m'
REPLACE = YELLOW = WARN = '\033[93m'
ENDC = '\033[0m'


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


def find_device(definitions, devname):
    "Find a given device in a server dict"
    for instname, inst in definitions["servers"].items():
        for classname, cls in inst.items():
            if devname in cls:
                return cls[devname], (instname, classname, devname)
    raise ValueError("device '%s' not defined" % devname)


def find_class(definitions, clsname):
    "Find a given device in a server dict"
    for instname, inst in definitions["servers"].items():
        if clsname in inst:
            return inst[clsname]
    raise ValueError("class '%s' not defined" % clsname)


def decode_pointer(ptr):
    """Take a string representing a JSON pointer and return a
    sequence of parts, decoded."""
    return [p.replace("~1", "/").replace("~0", "~")
            for p in ptr.split("/")]


def get_dict_from_db(db, data):

    """Takes a data dict, checks if any if the definitions are already
    in the DB and returns them."""

    dbdict = AppendingDict()

    for server_name, srvr in data.get("servers", {}).items():

        for class_name, cls in srvr.items():
            devices = db.get_device_name(server_name, class_name)

            for device_name in devices:
                name = device_name
                db_props = db.get_device_property_list(name, "*")
                dev = dbdict.servers[server_name][class_name][device_name]

                # Properties
                for prop in db_props:
                    value = db.get_device_property(name, prop)[prop]
                    value = [str(v) for v in value]  # is this safe?
                    dev.properties[prop] = value

                attr_props = cls.get(device_name, {}).get("attribute_properties")

                # Attribute properties
                if attr_props:
                    dbprops = db.get_device_attribute_property(device_name,
                                                               attr_props)
                    for attr, props in dbprops.items():
                        dev.attribute_properties[attr] = dict(
                            (prop, [str(v) for v in values])
                            for prop, values in props.items())  # whew!

    for class_name, cls in data.get("classes", {}).items():
        for prop in cls["properties"]:
            db_prop = db.get_class_property(class_name, prop)[prop]
            if db_prop:
                value = [str(v) for v in db_prop]
                dbdict.classes[class_name].properties[prop] = value

    return dbdict


class ObjectWrapper(object):

    """An object that allows all method calls and records them,
    then passes them on to a target object (if any)."""

    calls = []

    def __init__(self, target=None):
        self.target = target

    def __getattr__(self, attr):

        def method(attr, *args, **kwargs):
            self.calls.append((attr, args, kwargs))
            if self.target:
                getattr(self.target, attr)(*args, **kwargs)

        return partial(method, attr)
