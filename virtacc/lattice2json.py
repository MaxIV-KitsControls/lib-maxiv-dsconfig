#!/usr/bin/env python
# 	"$Name:  $";
# 	"$Header:  $";
#=============================================================================
#
# file :        lattice2json.py
#
# description : Python source for the lattice2json that is a tool to generate
#               a json file from an elegant lattice file
#               The json file can then be uploaded to a Tango database
#
# project :     Virtual Accelerator
#
# $Author:  $
#
# $Revision:  $
#
# $Log:  $
#
# copyleft :    Solaris/MAX IV
#               Krakow,PL/Lund,SE#               
#

from collections import defaultdict
import json
import os
import io
import sys
import re
from TangoProperties import TANGO_PROPERTIES

class SuperDict(defaultdict):
    "A recursive defaultdict with extra bells & whistles"
    	
    def __init__(self):
        defaultdict.__init__(self, SuperDict)
	
    def __setattr__(self, attr, value):
        self[attr] = value
	
    def __getattr__(self, attr):
        return self[attr]


class LatticeFileItem:
    ''' '''
    itemName = ""
    itemType = ''
    parameters = {}
    properties = {}
    
    def __init__(self, _line=''):
        '''
        Construct an object parsing a _line from a lattice file
        '''
        # print "Creating an item for the line:" 
        self.parameters= {}
        self.properties= {}
        # print _line
        
        # find a name
        colon_pos = _line.find(':')
        self.itemName = _line[:colon_pos].lstrip().rstrip().upper()
        
        # what left to be parsed
        line_left = _line[colon_pos + 1:].lstrip()        
            
        # find a type 
        param_name = ''  # the first item after a colon could be also a parameter name, like for a line element       
        eq_pos = line_left.find('=')        
        comma_pos = line_left.find(',')
        # let it work even there are no parameters defined - only element type
        if eq_pos < 0: eq_pos = len(line_left)
        if comma_pos < 0: comma_pos = len(line_left)        
        # so, we could read an element type
        self.itemType = line_left[:min(comma_pos, eq_pos)].rstrip().lower()
        
        # this is waiting to be processed:
        line_left = line_left[comma_pos + 1:].lstrip()
        
        # if the element type is also parameter name state this
        if eq_pos < comma_pos:  param_name = self.itemType          
        
        # parse the rest for parameters      
        while line_left != '':
            #print "PJB here1 ",  self.itemName, line_left, param_name
            if param_name != '':
                # searching for a value
                param_value = ''
                if line_left[0] == '(':
                    # value in brackets (may contain commas)
                    bracket_pos = line_left.index(')', 1)  # will rise an exception in case of badly formated line
                    # so, the value is (including brackets):
                    param_value = line_left[:bracket_pos + 1]
                    # this is what left to be parsed 
                    line_left = line_left[bracket_pos + 1:].lstrip()
                                        
                elif line_left[0] == '\"':
                    # value in quotes (could contain commas)
                    quote_pos = line_left.index('\"', 1)  # will rise an exception in case of badly formated line
                    # so, the value is (including quote):
                    param_value = line_left[:quote_pos + 1]
                    #print "PJB here2 ",   param_value, param_name

                    # this is what left to be parsed 
                    line_left = line_left[quote_pos + 1:].lstrip()
                else:
                    # typical case - the value between an equal and a comma characters
                    comma_pos = line_left.find(',')
                    if comma_pos < 0: comma_pos = len(line_left)
                    # a value, here you are
                    param_value = line_left[:comma_pos].rstrip()
                    # the following left to be parsed
                    line_left = line_left[comma_pos + 1:].lstrip()
                # store the parameter with the corresponding value 
                # print "PJB adding", param_name, param_value
                self.parameters[param_name] = param_value
                # PJB reset name back to empty here to find next parameter!(to enter else below)
                param_name=''
            else:
                # searching for a parameter 
                eq_pos = line_left.find('=')                 
                if eq_pos < 0: eq_pos = len(line_left)
                # allow value-less parameters
                comma_pos = line_left.find(',') 
                if comma_pos < 0: comma_pos = len(line_left)
                # so we know where to find parameter name
                param_name = line_left[:min(eq_pos, comma_pos)].rstrip().lower()
                # if the parameter has no value add it directly to the dictionary
                if comma_pos <= eq_pos:
                    self.parameters[param_name] = ''
                    param_name = ''                
                # this is what left to be parsed
                line_left = line_left[min(eq_pos, comma_pos) + 1:].lstrip()        
                             
        #print "Item name: "+self.itemName
        #print "Item type: "+self.itemType
        #print "Item parameters: ", self.parameters

    def match_properties(self):

        
        devclass = types_classes[self.itemType]
        print "in match_properties for class", devclass,  self.itemType
        # for given item type, look up required attributes and properties of tango
        if devclass in TANGO_PROPERTIES:
            fixed_properties_l =  list(TANGO_PROPERTIES[devclass][0].keys())
            print "fixed tango properties are ", fixed_properties_l
            lattice_properties_l = list(TANGO_PROPERTIES[devclass][1].keys())
            print "possible lattice tango properties are ", lattice_properties_l
            for k in self.parameters.keys():
                print "key", k
                #if not a required property or attribue then pop it
                if k.lower() not in lattice_properties_l:
                    self.parameters.pop(k)
                #otherwise rename key if an attribute
                if k.lower() in lattice_properties_l:
                    print "KEY ", k, TANGO_PROPERTIES[devclass][1][k], self.parameters[k]
                    self.parameters[TANGO_PROPERTIES[devclass][1][k]] = self.parameters.pop(k)
                    #if the property defines a dynamic attribute then set the value
                    if 'DYNAMIC_PROPERTIES' in TANGO_PROPERTIES[devclass][1][k]:
                        print "found dynamic property", TANGO_PROPERTIES[devclass][1][k]
                        if "DYNAMIC_PROPERTIES" not in self.parameters:
                            self.parameters["DYNAMIC_PROPERTIES"] = ""
                        #need to append dynamic properties
                        value=self.parameters[TANGO_PROPERTIES[devclass][1][k]]
                        self.parameters['DYNAMIC_PROPERTIES'] = self.parameters['DYNAMIC_PROPERTIES'] + (TANGO_PROPERTIES[devclass][1][k].split(':')[1].replace('XXX',value)) + ("\n")
                        self.parameters.pop(TANGO_PROPERTIES[devclass][1][k])
            # add the fixed properties
            self.parameters.update(TANGO_PROPERTIES[devclass][0])


        else:
            for k in self.parameters.keys():
                self.parameters.pop(k)

        print "parameters are now", self.parameters
        print "properties are now", self.properties
            

    def add_device(self, sdict, name_parsing_string='(?P<system>[a-zA-Z0-9]+)\.(?P<location>[a-zA-Z0-9]+)\.(?P<subsystem>[a-zA-Z0-9]+)\.(?P<device>[a-zA-Z0-9]+)\.(?P<num>[0-9]+)'):
        '''
        Updates json file
        '''
        # prepare pattern for parsing name
        pattern = re.compile(name_parsing_string)  

        #print "Item: " + self.itemName + " as " + self.itemType
        # only when we know class for certain element 

        if types_classes.has_key(self.itemType):

            # split name
            name_items = pattern.search(self.itemName) 
            if name_items == None:
                pass
                #print "Warning: Item name in lattice file doesn't match the naming convention."       
            else:
                system = name_items.group('system')
                subsystem = name_items.group('subsystem')
                location = name_items.group('location')
                device = name_items.group('device')
                num = name_items.group('num')
                if num == None: num = ''
                # print "Parsed elements: "+system+", "+subsystem+ ", "+location+","+device+","+num

                #store the parameters we need (attributes and properties)
                #print "PJB parameter",  self.itemName, self.parameters
                self.match_properties()

                # create device for json output
                name = (system+"."+location + '/' + subsystem + '/' + device + num).encode('ascii', 'ignore')
                devclass = types_classes[self.itemType].encode('ascii', 'ignore')
                server = devclass + '/' + system+"."+location
                print "+++++++++++++++++ Creating device server : " + server + " for " + devclass + " (name= " + name    + ")" 
                print "+++++++++ With properties : ", self.parameters
                #print "+++++++++ With attributes : ", self.parameters
                # Dont actually write attributes to DB, only properties
                # see if this class exists and append if so, or create
                devdict = sdict.servers["%s/%s" % (devclass, system+"."+location)][devclass][name]
                devdict.properties = self.parameters

                
class ElegantLatticeParser:
    ''' Class for parsing an elegant lattice file. '''
    fileName = ""
    file = None
    items = []     

    def __init__(self, _fileName):
        '''Constructs a parser object.

        Keyword arguments:
        _fileName -- the name of file to be parsed        
        '''
        self.fileName = _fileName
        self.file = io.open(_fileName)

    def parseLatticeFile(self):
        ''' '''        
        line = ""  # this will be a line combined from lines to be connected
        for ll in self.file:
            l = ll.lstrip().rstrip()
            if len(l) > 0:
                if l[0] == '!':
                    pass  # do not process comments 
                elif l[0] == '%':
                    pass  # processing RPNs are not implemented
                elif l[-1] == '&':
                    # Combine lines to be concated
                    line = line + ' ' + l[:-1] 
                else:
                    # So this is the last line to be combined 
                    line = line + l                
                    # Create an object and add it to list
                    self.items.append(LatticeFileItem(line.lstrip().rstrip())) 
                    line = ""



if __name__ == '__main__':
    
    inFileName = ''
    
    #configuration
    #update_values = False
    #update_properties = False
    #test_mode = False
    
    # define classes for lattice elements
    types_classes = {}
    types_classes["dip"] = "VAMagnet"
    types_classes["csrcsbend"] = "VAMagnet"
    types_classes["kquad"] = "VAMagnet"
    types_classes["sext"] = "VAMagnet"
    types_classes["hkick"] = "VACorrector"
    types_classes["vkick"] = "VACorrector"
    types_classes["monitor"] = "VABPM"
    types_classes["watch"] = "VAYAGScreen"
    types_classes["rfcw"] = "VARfCavity"
    
    #read arguments
    for par in sys.argv[1:]:
        #if par[0:2] == '--':
        #    if par == '--update-values':
        #        update_values = True
        #    elif par == '--update-properties':
        #        update_properties = True
        #    elif par == '--test-mode':
        #        test_mode = True
        #elif inFileName == '':
        inFileName = par
    
    # create a parser for the file        
    parser = ElegantLatticeParser(inFileName)     
    
    # parse the file
    parser.parseLatticeFile()
    parser.file.close()
   
    
    # make a json file
    json_dict = SuperDict()
    for item in parser.items:

        #PJB hack to deal with magnet circuits here, should really go where other
        #properties set
        #if "CR" in item.itemName and "_" in item.itemName:
        #    magnet,circuit = item.itemName.split("_")
        #    #print "found circuit device magnet", magnet, circuit
        #    # if it is a circuit, add the circuit as a property!
        #    item.properties["circuit"] = circuit
            
        item.add_device(json_dict)
    #print json.dumps(json_dict, indent=4)

    outfile = open('lattice.json', 'w')
    json.dump(json_dict, outfile, indent=4)


    #!! note that item has parameters, but only want to extract those needed for tango!


