"""
This is a bunch of providers for the faker (a.k.a fake-factory)
module, which generates randomized data of various formats.

This module can generate dsconfig format configurations that
are valid (hopefully) and at least vaguely convincing.

Usage:

>>> from faker import Faker
>>> from providers import TangoProvider
>>> fake = Faker()
>>> fake.add_provider(TangoProvider)
>>> cfg = fake.tango_database()

"""

from string import ascii_uppercase, digits
from random import randint, expovariate, choice
from math import ceil

from faker import Faker
from faker.providers import BaseProvider

from dsconfig.tangodb import (PROTECTED_PROPERTIES,
                              SPECIAL_ATTRIBUTE_PROPERTIES)


class TangoProvider(BaseProvider):

    "Provide fake dsconfig Tango configurations"

    def tango_property(self):
        n = randint(1, 5)
        name = str("".join(_fake.word().capitalize() for i in range(n)))

        n = int(ceil(expovariate(1)))  # usually 1, sometimes larger
        value = [str(_fake.user_name()) for i in range(n)]

        return name, value

    def tango_attribute_property(self):
        name = choice(SPECIAL_ATTRIBUTE_PROPERTIES)
        value = [str(randint(-100, 100))]
        return name, value

    def tango_attribute_config(self):
        n = randint(1, 3)
        attr_name = str("".join(_fake.word().capitalize() for i in range(n)))
        n_props = int(ceil(expovariate(1)))  # usually 1, sometimes larger
        attr_props = dict(_fake.tango_attribute_property()
                          for i in range(n_props))
        return attr_name, attr_props

    def tango_device(self):
        name = str("{0}/{1}/{2}".format(*_fake.words(3))).upper()
        name = name + "-" + str(randint(0, 10))

        n_devprops = int(ceil(expovariate(1)))  # usually 1, sometimes larger
        devprops = dict(_fake.tango_property()
                        for i in range(n_devprops))

        n_attrcfg = int(ceil(expovariate(1))) - 1
        attrprops = dict(_fake.tango_attribute_config()
                         for i in range(n_attrcfg))

        value = {"properties": devprops}
        if attrprops:
            value["attribute_properties"] = attrprops
        return name, value

    def tango_device_class(self):
        n = randint(1, 3)
        name = str("".join(_fake.word().capitalize() for i in range(n)))

        n_devs = int(ceil(expovariate(1)))
        devices = dict(_fake.tango_device() for i in range(n_devs))
        return name, devices

    def tango_class(self):
        n = randint(1, 3)
        name = str("".join(_fake.word().capitalize() for i in range(n)))

        n_devprops = int(ceil(expovariate(1)))  # usually 1, sometimes larger
        devprops = dict(_fake.tango_property()
                        for i in range(n_devprops))

        n_attrcfg = int(ceil(expovariate(1))) - 1
        attrprops = dict(_fake.tango_attribute_config()
                         for i in range(n_attrcfg))

        value = {"properties": devprops}
        if attrprops:
            value["attribute_properties"] = attrprops

        return name, value

    def tango_instance(self):
        n = randint(1, 3)
        chars = ascii_uppercase + digits
        name = "-".join("".join(choice(chars)
                                for i in range(randint(1, 5)))
                        for j in range(n))

        n_classes = int(ceil(expovariate(1)))
        value = dict(_fake.tango_device_class() for i in range(n_classes))
        return name, value

    def tango_server(self):
        n = randint(1, 3)
        name = "".join(_fake.word().capitalize() for i in range(n))

        n_instances = randint(1, 10)
        value = dict(_fake.tango_instance() for i in range(n_instances))

        return name, value

    def tango_database(self, servers=(5, 20), classes=(1, 5)):
        n_servers = randint(*servers)
        servers = dict(_fake.tango_server() for i in range(n_servers))
        n_classes = randint(*classes)
        classes = dict(_fake.tango_class() for i in range(n_classes))
        value = {"_title": "MAX-IV Tango JSON intermediate format",
                 "_source": str(_fake.file_name(extension="xls")),
                 "_date": str(_fake.date_time()),
                 "servers": servers}
        if classes:
            value["classes"] = classes
        return value


_fake = Faker()
_fake.add_provider(TangoProvider)
