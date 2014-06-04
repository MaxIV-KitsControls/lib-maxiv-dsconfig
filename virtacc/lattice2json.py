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
from PowerSupplyMap import POWER_SUPPLY_MAP
import copy

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

        #self.itemName = self.itemName.replace('.','-')

        print "name", self.itemName
        
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
        print "in match_properties for class", devclass,  self.itemName

        if "CIR" in self.itemName:
            print "properties for magnet circuit"
            #self.parameters["powersupply"] = ""
            #self.parameters["magnets"] = ""

        # for given item type, look up required attributes and properties of tango
        elif devclass in TANGO_PROPERTIES:
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
                    self.parameters[TANGO_PROPERTIES[devclass][1][k]] = [self.parameters.pop(k)]
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

        if "MAG" in self.itemName:
            self.parameters["Type"] = self.itemType

        print "parameters are now", self.parameters
        print "properties are now", self.properties
            
    #def add_device(self, sdict, name_parsing_string='(?P<system>[a-zA-Z0-9]+)\.(?P<location>[a-zA-Z0-9]+)\.(?P<subsystem>[a-zA-Z0-9]+)\.(?P<device>[a-zA-Z0-9]+)\.(?P<num>[0-9]+)\.(?P<cir>[a-zA-Z0-9]+)'):
    def add_device(self, sdict, name_parsing_string='(?P<system>[a-zA-Z0-9]+)\.(?P<location>[a-zA-Z0-9]+)\.(?P<subsystem>[a-zA-Z0-9]+)\.(?P<device>[a-zA-Z0-9]+)\.(?P<num>[0-9]+)'):
        '''
        Updates json file
        '''
        # prepare pattern for parsing name
        pattern = re.compile(name_parsing_string)  

        print "Item: " + self.itemName + " as " + self.itemType
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
                #circuit = name_items.group('cir')   
                
                #print "circuit is ", circuit

                if num == None: num = ''
                # print "Parsed elements: "+system+", "+subsystem+ ", "+location+","+device+","+num

                num2 =  "%02d" % int(num)

                #store the parameters we need (attributes and properties)
                #print "PJB parameter",  self.itemName, self.parameters
                print "++++++++++++++++++++++++++++ DEALING WITH: " + self.itemName

                self.match_properties()

                # create device for json output
                name = (system+"-"+location + '/' + subsystem + '/' + device + "-" +num2).encode('ascii', 'ignore')
                devclass = types_classes[self.itemType].encode('ascii', 'ignore')
                server = devclass + '/' + system+"-"+location

                #hack for circuits
                if "CIR" in self.itemName:
                    print "orig name",self.itemName, name
                    #name = name.split("-",1)[-1] + "-CIR" +  "-" +num2
                    name = name.rsplit("-",1)[0] + "-CIR" +  "-" +num2
                    #pdevclass = "Circuit"
                    devclass = "MagnetCircuit"

                print "+++++++++++++++++ Creating device server : " + server + " for " + devclass + " (name= " + name    + ")" 
                print "+++++++++ With properties : ", self.parameters
                #print "+++++++++ With attributes : ", self.parameters
                # Dont actually write attributes to DB, only properties
                # see if this class exists and append if so, or create
                devdict = sdict.servers["%s/%s" % (devclass, system+"-"+location)][devclass][name]

                if "MAG" in self.itemName and "CIR" not in self.itemName:
                    print "-------------------- FOUND MAGNET", self.itemName

                    #see what is the ps of the magnet
                    powersupplyname = POWER_SUPPLY_MAP[name]

                    #create circuit device for each new ps
                    print "circuit_ps_list", circuit_ps_list

                    #copy the magnet and call recursively add device!
                    magnetcircuit = copy.deepcopy(self)
                    magnetcircuit.itemName = self.itemName + ".CIR"

                    magnetcircuit.parameters = {}
                    magnetcircuit.parameters['PowerSupply'] = [powersupplyname]
                    magnetcircuit.parameters['Magnets'] = [name]
                    
                    #assign circuit name as property of magnet device
                    #no regex to fix name here so do by hand
                    #e.g. I.BC1.MAG.COEX.4.CIR -> I-BC1/MAG/COEX-CIR-04
                    cname = magnetcircuit.itemName.replace(".","/")
                    cname = cname.replace("/","-",1)
                    cname = name.rsplit("/CIR",1)[0]
                    cname = cname.rsplit("-",1)[0] + "-CIR-" + cname.rsplit("-",1)[1]

                    #only add one circuit device per ps
                    if powersupplyname not in circuit_ps_list:
                        
                        magnetcircuit.add_device(sdict)
                        circuit_ps_list[powersupplyname] = cname 

                        print "adding circuit name ", magnetcircuit.itemName, cname

                        self.parameters['Circuit'] = [cname]
                        
                    else:
                        #if we aleady made this circuit device, add it to this magnet properties
                        print "!!!ALART!!! already added a circuit device for ", self.itemName
                        
                        self.parameters['Circuit'] = [circuit_ps_list[powersupplyname]]

                        #need to get the name of the circuit device from the ps dict though
                        print "exiting circuit device is", circuit_ps_list[powersupplyname]
                        
                        
                        #current_mags = sdict.servers["%s/%s" % (devclass, system+"-"+location)][devclass][circuit_ps_list[powersupplyname]].properties
                        current_mags = sdict.servers["%s/%s" % ("MagnetCircuit", system+"-"+location)]["MagnetCircuit"][circuit_ps_list[powersupplyname]].properties
                        current_mags['Magnets'].append(name)
                        

                        print "props", current_mags['Magnets']

                        #if already have a circuit device, magnet must have sisters
                        #self.parameters['Sisters'].append('bill')

                
                    #circuitname = name + "circuit"
                    #circuitdevclass = devclass + "circuit"
                    #circuitserver = server+ "circuit"
                    #


                    #self.parameters["PowerSupply"] = [powersupplyname]
                    # self.parameters["Circuit"] = [powersupplyname]
                    #print  item.properties["powersupply"]
            
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
    types_classes["dip"] = "Magnet"
    types_classes["csrcsbend"] = "Magnet"
    types_classes["sole"] = "Magnet"
    types_classes["kquad"] = "Magnet"
    types_classes["ksext"] = "Magnet"
    types_classes["hkick"] = "Magnet" 
    types_classes["vkick"] = "Magnet"
    #types_classes["hkick"] = "VACorrector"
    #types_classes["vkick"] = "VACorrector"
    types_classes["monitor"] = "VABPM"
    types_classes["watch"] = "VAYAGScreen"
    types_classes["rfcw"] = "VARfCavity"
    
    circuit_ps_list = {}

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
        if "MAG" in item.itemName:
            print "----------------------- found magnet device", item.itemName
         #    # hence also create a magnet circuit device
            

        item.add_device(json_dict)
    #print json.dumps(json_dict, indent=4)

    #now we have the dict, loop over again and sort out magnets, power supplies and circuits

    print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ "
    print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ "
    print json_dict.servers

    outfile = open('lattice.json', 'w')
    json.dump(json_dict, outfile, indent=4)


    #!! note that item has parameters, but only want to extract those needed for tango!


