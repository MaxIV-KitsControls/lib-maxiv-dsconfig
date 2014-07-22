###############################################################################
##     DsGenerator module will generate a set of tango device servers for
##     your system. Taking as an input a file to parse.
##
##     Copyright (C) 2013  Antonio Milan Otero
##
##     This program is free software: you can redistribute it and/or modify
##     it under the terms of the GNU General Public License as published by
##     the Free Software Foundation, either version 3 of the License, or
##     (at your option) any later version.
##
##     This program is distributed in the hope that it will be useful,
##     but WITHOUT ANY WARRANTY; without even the implied warranty of
##     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##     GNU General Public License for more details.
##
##     You should have received a copy of the GNU General Public License
##     along with this program.  If not, see [http://www.gnu.org/licenses/].
###############################################################################

from lattice2json_properties import TANGO_ATTRIBUTES

class DeviceServerInfo():
    """This class will store the basic information related to a device server
    """

    def __init__(self, className=None,
                       serverInst=None,
                       name=None,
                       properties=None):
        if className is not None:
            self.className = className
        else:
            self.className = ''
        if serverInst is not None:
            self.serverInst = serverInst
        else:
            self.serverInst = ''
        if name is not None:
            self.name = name
        else:
            self.name = ''
        if properties is not None:
            self.properties = properties
        else:
            self.properties = {}

    def getClass(self):
        return self.className

    def setClass(self, className):
        self.className = className

    def getServerInst(self):
        return self.serverInst

    def setServerInst(self, serverInst):
        self.serverInst = serverInst

    def getName(self):
        return self.name

    def setName(self, name):
        self.name = name

    def getProperties(self):
        return self.properties

    def addProperty(self, prop):
        self.properties.append(prop)


    def match_attributes(self):
        print "in match attributes"
        devclass = self.className
        print "in match_properties for class", devclass, self.name
        # for given item type, look up required attributes and properties of tango
        if devclass in TANGO_ATTRIBUTES:
            attributes_l =  list(TANGO_ATTRIBUTES[devclass].keys())
            print "tango attributes are ", attributes_l
            for k in self.properties.keys():
                print "key", k
                #if not a required property or attribute then pop it
                if k not in attributes_l:
                    self.properties.pop(k)
                #otherwise rename key if an attribute
                if k in attributes_l:
                    print "KEY ", k, TANGO_ATTRIBUTES[devclass][k], self.properties[k]
                    self.properties[TANGO_ATTRIBUTES[devclass][k]] = self.properties.pop(k)
            return True
        else:
            return False
