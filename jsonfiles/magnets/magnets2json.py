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
import numpy as np

cirlist = []
cirlist2 = []
nextdev = True
testpjb = 999
#lastcir = "xxx"
#currentcir = ""

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
    alpars= {}
    lastdev = "x"

    
    def __init__(self, _line=''):
        '''
        Construct an object parsing a _line from a lattice file
        '''
        self.psparameters= {}
        self.parameters= {}
        self.properties= {}



        print "IN INIT", self.lastdev
        
        # find a name
        colon_pos = _line.find(':')
        self.itemName = _line[:colon_pos].lstrip().rstrip().upper()

        #self.itemName = self.itemName.replace('.','-')

        
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
                             


    def match_properties(self):

        
        devclass = types_classes[self.itemType]

        if "CIR" in self.itemName:
             print "dealing with magnet circuit"
        #    #self.parameters["powersupply"] = ""
        #    #self.parameters["magnets"] = ""

        # for given item type, look up required attributes and properties of tango
        elif devclass in TANGO_PROPERTIES:

            fixed_properties_l =  list(TANGO_PROPERTIES[devclass][0].keys())
            #print "fixed tango properties are ", fixed_properties_l

            # add the fixed properties
            self.parameters.update(TANGO_PROPERTIES[devclass][0])

            lattice_properties_l = list(TANGO_PROPERTIES[devclass][1].keys())
            #print "possible lattice tango properties are ", lattice_properties_l
            for k in self.parameters.keys():
                #print "key", k
                #if not a required property or attribue then pop it
                if k.lower() not in lattice_properties_l and k not in  fixed_properties_l:
                    #print "popping ", k
                    self.parameters.pop(k)

                #otherwise rename key if an attribute
                if k.lower() in lattice_properties_l:
                    #print "KEY ", k.lower(), TANGO_PROPERTIES[devclass][1][k.lower()], self.parameters[k]
                    self.parameters[TANGO_PROPERTIES[devclass][1][k.lower()]] = [self.parameters.pop(k)]
                    #if the property defines a dynamic attribute then set the value
                    #if 'DYNAMIC_PROPERTIES' in TANGO_PROPERTIES[devclass][1][k]:
                    #    print "found dynamic property", TANGO_PROPERTIES[devclass][1][k]
                    #    if "DYNAMIC_PROPERTIES" not in self.parameters:
                    #        self.parameters["DYNAMIC_PROPERTIES"] = ""
                    #    #need to append dynamic properties
                    #    value=self.parameters[TANGO_PROPERTIES[devclass][1][k]]
                    #    self.parameters['DYNAMIC_PROPERTIES'] = self.parameters['DYNAMIC_PROPERTIES'] + (TANGO_PROPERTIES[devclass][1][k].split(':')[1].replace('XXX',value)) + ("\n")
                    #    self.parameters.pop(TANGO_PROPERTIES[devclass][1][k])




        else:
            for k in self.parameters.keys():
                self.parameters.pop(k)

        if "MAG" in self.itemName and not "CIR" in self.itemName:
            self.parameters["Type"] = self.itemType

        #print "parameters are now", self.parameters
        #print "properties are now", self.properties
            
    #def add_device(self, sdict, name_parsing_string='(?P<system>[a-zA-Z0-9]+)\.(?P<location>[a-zA-Z0-9]+)\.(?P<subsystem>[a-zA-Z0-9]+)\.(?P<device>[a-zA-Z0-9]+)\.(?P<num>[0-9]+)\.(?P<cir>[a-zA-Z0-9]+)'):
    def add_device(self, sdict, adict, psdict, name_parsing_string='(?P<system>[a-zA-Z0-9]+)\.(?P<location>[a-zA-Z0-9]+)\.(?P<subsystem>[a-zA-Z0-9]+)\.(?P<device>[a-zA-Z0-9]+)\.(?P<num>[0-9]+)'):
        '''
        Updates json file
        '''
        # prepare pattern for parsing name
        pattern = re.compile(name_parsing_string)  

        print "In add device for item: " + self.itemName + " as " + self.itemType, self.lastdev, self.alpars, testpjb
        # only when we know class for certain element 

        print "adict is ", adict

        #for case with no final number like I.TR1.MAG.DIE (no .1 etc at end)
        alt_name_parsing_string='(?P<system>[a-zA-Z0-9]+)\.(?P<location>[a-zA-Z0-9]+)\.(?P<subsystem>[a-zA-Z0-9]+)\.(?P<device>[a-zA-Z0-9]+)'
        alt_pattern = re.compile(alt_name_parsing_string)  

        #self.alpars = {}
        devdictalarm = None

        if types_classes.has_key(self.itemType):

            print "" 
            print "" 

            # split name
            name_items = pattern.search(self.itemName) 
            parsed=False
            tryagain=False
            if name_items == None:
                print "Warning: Item name in lattice file doesn't match the naming convention.",self.itemName       
                tryagain=True
            else:
                parsed=True
            if tryagain:
                name_items = alt_pattern.search(self.itemName) 
                if name_items == None:
                    print "Warning: Item name in lattice file STILL doesn't match the naming convention.",self.itemName
                else:
                    parsed=True
            if parsed:
                system = name_items.group('system')
                subsystem = name_items.group('subsystem')
                location = name_items.group('location')
                device = name_items.group('device')
                
                if tryagain==False:
                    num = name_items.group('num')   
                else:
                    num=""
                #circuit = name_items.group('cir')   
                
                #print "circuit is ", circuit

                if num == None: num = ''
                # print "Parsed elements: "+system+", "+subsystem+ ", "+location+","+device+","+num

                if num != "":
                    num2 =  "%02d" % int(num)
                else:
                    num2 = "01"

                print "num 2 is ", num2
                #store the parameters we need (attributes and properties)
                #print "PJB parameter",  self.itemName, self.parameters
                #print "++++++++++++++++++++++++++++ DEALING WITH: " + self.itemName

                self.match_properties()

                # create device for json output
                name = (system+"-"+location + '/' + subsystem + '/' + device + "-" + num2).encode('ascii', 'ignore')
                devclass = types_classes[self.itemType].encode('ascii', 'ignore')
                server = devclass + '/' + system+"-"+location

                #hack for circuits
                if "CIR" in self.itemName:
                    print "orig name",self.itemName, name
                    #name = name.split("-",1)[-1] + "-CIR" +  "-" +num2
                    #name = name.rsplit("-",1)[0] + "-CIR" +  "-" +num2

                    #quad circuits named like CRQ
                    #correctors like CRCOX and CRCOY
                    #dipoles like CRDI
                    #solenoid like CRSOL
                    #sextu like CRX
                    endname = name.rsplit("/",1)[1]
                    print "endname is ", endname
                    #hack for bc1
                    if "QD" in self.itemName and "BC1" in self.itemName:
                        endname = "CRQM-" +num2 
                    #hack for bc2
                    elif "QF" in self.itemName and "BC2" in self.itemName and "3" not in self.itemName and "4" not in self.itemName and "5" not in self.itemName:
                        endname = "CRQM-" +num2 
                    elif "QF" in self.itemName and "BC2" in self.itemName and ("3" in self.itemName or "5" in self.itemName):
                        endname = "CRQ1-01"
                    elif "QF" in self.itemName and "BC2" in self.itemName and "4" in self.itemName:
                        endname = "CRQ2-01"
                    #
                    elif "Q" in self.itemName:
                        endname = "CRQ-" + num2 
                    elif "CO" in self.itemName and "X" in self.itemName:
                        endname = "CRCOX-" + num2
                    elif "CO" in self.itemName and "Y" in self.itemName:
                        endname = "CRCOY-" + num2
                    elif "DI" in self.itemName:
                        endname = "CRDI-" + num2 
                    elif "SX" in self.itemName:
                        endname = "CRSX-" + num2 
                    elif "SOL" in self.itemName:
                        endname = "CRSOL-" + num2
                    elif "SM" in self.itemName:
                        endname = "CRSM-" + num2
                    else:
                        sys.exit("Cannot convert circuit name" + self.itemName)

                    if "/" in endname: #in case did not end with number, endname will be some */*/ by mistake
                        endname=endname.split("-")[0]+"-01"

                    name = name.rsplit("/",1)[0] + "/" + endname


                    #e.g in G00 have COIX 1, 2, 3 and COHX 1 and 2, which would make COX 1, 2, 3 with COIX 1 and 2 being lost!
                    #increment number till unique
                    while name in cirlist:
                        print "danger! already named this circuit!", self.itemName, name
                        suffix = int(name.split("-")[2]) + 1
                        newnum2 =  "%02d" % suffix
                        print newnum2
                        name = (name.rsplit("-",1)[0]) + "-" + newnum2
                        print name
                    print "new name ", name
                    cirlist.append(name)
                    print cirlist
                    devclass = "MagnetCircuit"


                print "+++++++++++++++++ Creating device server : " + server + " for " + devclass + " (name= " + name    + ")" 
                print "+++++++++ With properties : ", self.parameters
                #print "+++++++++ With attributes : ", self.parameters
                # Dont actually write attributes to DB, only properties
                # see if this class exists and append if so, or create
                devdict = sdict.servers["%s/%s" % (devclass, system+"-"+location)][devclass][name]

                #for circuit json only
                if "CR" in name:
                    psdevdict = psdict.Circuits[name]


                if "MAG" in self.itemName and "CIR" not in self.itemName:


                    
                    #compact name is to find tag in plc alarms
                    name_l = self.itemName.split(".")
                    section = name_l[1]
                    del name_l[0]
                    del name_l[1]
                    compactfullname = "".join(name_l)
                    compactname = compactfullname.split("_")[0]
                    #compactcirname = compactfullname.split("_")[1]

                        
                    print "-------------------- magnet not circuit", self.itemName,  compactname

                    #global lastcir
                    #global currentcir
                           
                    #print section

                    #see what is the ps of the magnet
                    if name in POWER_SUPPLY_MAP:
                        powersupplyname = POWER_SUPPLY_MAP[name]
                    else:
                        print "magnet not in PS map, skipping", name
                        return 

                    #create circuit device for each new ps
                    #print "circuit_ps_list", circuit_ps_list

                    #copy the magnet and call recursively add device!
                    magnetcircuit = copy.deepcopy(self)
                    magnetcircuit.itemName = self.itemName + ".CIR"

                    magnetcircuit.parameters = {}
                    magnetcircuit.parameters['PowerSupplyProxy'] = [powersupplyname]
                    magnetcircuit.parameters['MagnetProxies'] = [name]
                    magnetcircuit.parameters['RiseTime'] = [0.0]
                    magnetcircuit.parameters['ResistanceReference'] = [0.0]
                    magnetcircuit.parameters['CoilNames'] = [""]

                    #for the ps json file only
                    magnetcircuit.psparameters['PowerSupplyProxy'] = [powersupplyname]
                    magnetcircuit.psparameters['MagnetProxies'] = [name]

                    #get alarm info from excel
                    pyalarm = system+"-"+location + '/MAG/ALARM'

                    print "adict is again", adict
                    if adict is not None:
                        devdictalarm = adict.servers["%s/%s" % ("PyAlarm", "I-MAG")]["PyAlarm"][pyalarm]
                        print "init devdictalarm"

                    #print "made dev dict ", devdictalarm
                    for key in alarm_dict:
                        if compactname in key:


                            print "alarm device ", pyalarm, self.lastdev
                            self.nextdev=False
                            if pyalarm!=self.lastdev:
                                print "setting"
                                self.lastdev = pyalarm
                                self.nextdev = True
                            print "new alarm ", self.nextdev, self.lastdev                            

                            pyattname = "I-" + section + "/DIA/COOLING"

                            print "alarm dict is ", alarm_dict
                            print "key is ", key
                            print "alarm dict entry is ", alarm_dict[key]
                            print "FOUND ALARM INFO FOR ", compactname, key, alarm_dict[key], pyattname, adict

                            #for the magnets json file
                            self.parameters['TemperatureInterlock'] = [pyattname, key, alarm_dict[key]]
                            #self.parameters['TemperatureInterlock'] = ["i-k04/mag/plc-01", key, alarm_dict[key]]

                            #for the alarms json file

                            #if adict is not None:

                            #print "devdictalarm", devdictalarm

                            alname = 'TemperatureInterlock'+key.split('_')[-2]+'_'+system+"_"+location+'__'+'MAG'+'__'+ device + "_" +num2
                            alsev = alname+":"+"ALARM"
                            alrec = alname+":"+"HTML"
                            aldesc = alname+":"+alarm_dict[key]

                            if pyalarm not in self.alpars:
                                self.alpars[pyalarm] = {}

                            if "AlarmList" not in self.alpars[pyalarm]:
                                self.alpars[pyalarm]["AlarmList"] = []
                            self.alpars[pyalarm]['AlarmList'].append(alname+":"+pyattname+"/"+key)

                            if "AlarmSeverity" not in self.alpars[pyalarm]:
                                self.alpars[pyalarm]["AlarmSeverity"] = []
                            self.alpars[pyalarm]['AlarmSeverity'].append(alsev)

                            if "AlarmDescriptions" not in self.alpars[pyalarm]:
                                self.alpars[pyalarm]["AlarmDescriptions"] = []
                            self.alpars[pyalarm]['AlarmDescriptions'].append(aldesc)

                            if "AlarmReceivers" not in self.alpars[pyalarm]:
                                self.alpars[pyalarm]["AlarmReceivers"] = []
                            self.alpars[pyalarm]['AlarmReceivers'].append(alrec)

                            if "StartupDelay" not in self.alpars[pyalarm]:
                                self.alpars[pyalarm]["StartupDelay"] = [0.0]
                            
                            if "AutoReset" not in self.alpars[pyalarm]:
                                self.alpars[pyalarm]["AutoReset"] = [60.0]
                            
                            if "MaxMessagesPerAlarm" not in self.alpars[pyalarm]:
                                self.alpars[pyalarm]["MaxMessagesPerAlarm"] = [1]
                            
                            if "PollingPeriod" not in self.alpars[pyalarm]:
                                self.alpars[pyalarm]["PollingPeriod"] = [5]
                            
                            if "LogFile" not in self.alpars[pyalarm]:
                                self.alpars[pyalarm]["LogFile"] = ["/tmp/pjb/log"]
                            
                            if "HtmlFolder" not in self.alpars[pyalarm]:
                                self.alpars[pyalarm]["HtmlFolder"] = ["/tmp/pjb"]
                            
                            if "AlarmThreshold" not in self.alpars[pyalarm]:
                                self.alpars[pyalarm]["AlarmThreshold"] = [1]


                                
                    #if self.nextmag:       
                        #print "FIX THE PROPERTIES for ", devdictalarm
                            print "devdictalarm is ", devdictalarm
                            devdictalarm.properties = self.alpars[pyalarm]
                        #reset alarm pars
                     #self.alpars = {}

                    polarity = 1
                    orientation = 1
                    #get calibration info from the excel
                    if self.itemName.split("_")[0] in calib_dict:
                        print "FOUND CALIB INFO", self.itemName
                        #find max multipole expansions
                        dim = max(calib_dict[self.itemName.split("_")[0]].keys(), key=int)

                        print "--- max order is", dim

                        #create arrays of this dimensions
                        #other dimension is 11

                        fieldsmatrix = [[0 for x in xrange(11)] for x in xrange(dim)] 
                        #print fieldsmatrix
                        currentsmatrix = [[0 for x in xrange(11)] for x in xrange(dim)] 
                        #print currentsmatrix

                        #fieldsmatrix = np.zeros(shape=(dim,11), dtype=float) 
                        #currentsmatrix = np.zeros(shape=(dim,11), dtype=float) 
                        #print fieldsmatrix

                        #iterate over keys and add to the array
                        for key in calib_dict[self.itemName.split("_")[0]]:
                            print '--- ', key, 'corresponds to', calib_dict[self.itemName.split("_")[0]][key]
                            currents = calib_dict[self.itemName.split("_")[0]][key][5:16]
                            fields   = calib_dict[self.itemName.split("_")[0]][key][17:28]
                            print '--- ',currents, fields

                            fieldsmatrix[key-1]=fields
                            currentsmatrix[key-1]=currents
                            #key here is the multipole order. any one should have same polarity
                            polarity = calib_dict[self.itemName.split("_")[0]][key][2]
                            orientation = calib_dict[self.itemName.split("_")[0]][key][3]
                            #print "P, O", polarity, orientation

                        print '--- ',fieldsmatrix
                        print '--- ',currentsmatrix

                        #now trim the matrices (lists)
                        maxlength = 11
                        for i,val in enumerate(fieldsmatrix[dim-1]):
                            if val=='':
                                print i , val
                                maxlength = i
                                break
                        print maxlength
                        for i in xrange(dim):
                            print i
                            del fieldsmatrix[i][maxlength:]
                            del currentsmatrix[i][maxlength:]

                        print 'Now--- ',fieldsmatrix
                        print 'Now--- ',currentsmatrix

                        #if "_" in self.itemName and "CR" in self.itemName:
                        #    currentcir = self.itemName.split("_")[1]
                        #    print "actually circuit info",  currentcir, lastcir
                        #    if currentcir != lastcir:
                        #        lastcir = currentcir
                        #        print "new cir",  currentcir, lastcir

                        #currents = calib_dict[self.itemName][5:16]
                        #fields   = calib_dict[self.itemName][16:27]
                        #if "" not in currents and "" not in fields:
                        magnetcircuit.parameters['ExcitationCurveCurrents']= currentsmatrix
                        magnetcircuit.parameters['ExcitationCurveFields']= fieldsmatrix
                        #magnetcircuit.parameters['Orientation'] = orientation
                        #magnetcircuit.parameters['Polarity']    = polarity
                    self.parameters['Orientation'] = int(orientation)
                    self.parameters['Polarity']    = int(polarity)

                    #assign circuit name as property of magnet device
                    #no regex to fix name here so do by hand
                    #e.g. I.BC1.MAG.COEX.4.CIR -> I-BC1/MAG/COEX-CIR-04


                    cname = magnetcircuit.itemName.replace(".","/")

                    print "dealing with cname 1 ", cname

                    cname = cname.replace("/","-",1)

                    print "dealing with cname 2 ", cname

                    cname = name.rsplit("/CIR",1)[0]

                    print "dealing with cname 3 ", cname

                    endname = cname.rsplit("/",1)[1]


                    #hack for bc1
                    if "QD" in self.itemName and "BC1" in self.itemName:
                        endname = "CRQM-" +  cname.rsplit("-",1)[1]
                    #
                    #hack for bc2
                    elif "QF" in self.itemName and "BC2" in self.itemName and "3" not in self.itemName and "4" not in self.itemName and "5" not in self.itemName:
                        endname = "CRQM-" +  cname.rsplit("-",1)[1]
                    elif "QF" in self.itemName and "BC2" in self.itemName and ("3" in self.itemName or "5" in self.itemName):
                        endname = "CRQ1-01"
                    elif "QF" in self.itemName and "BC2" in self.itemName and "4" in self.itemName:
                        endname = "CRQ2-01"
                    #
                    elif "Q" in self.itemName:
                        endname = "CRQ-" +  cname.rsplit("-",1)[1]
                    elif "CO" in self.itemName and "X" in self.itemName:
                        endname = "CRCOX-" +  cname.rsplit("-",1)[1]
                    elif "CO" in self.itemName and "Y" in self.itemName:
                        endname = "CRCOY-" +  cname.rsplit("-",1)[1]
                    elif "DI" in self.itemName:
                        endname = "CRDI-" +  cname.rsplit("-",1)[1]
                        print "dealing with endname  ", endname
                    elif "SX" in self.itemName:
                        endname = "CRSX-" +  cname.rsplit("-",1)[1]
                    elif "SOL" in self.itemName:
                        endname = "CRSOL-" +  cname.rsplit("-",1)[1]
                    elif "SM" in self.itemName:
                        endname = "CRSM-" +  cname.rsplit("-",1)[1]
                    else:
                        sys.exit("Cannot convert circuit name" + self.itemName)

                    if "/" in endname: #in case did not end with number, endname will be some */*/ by mistake
                        endname=endname.split("-")[0]+"-01"

                    cname = cname.rsplit("/",1)[0] + "/" + endname
                    #cname = cname.rsplit("-",1)[0] + "-CIR-" + cname.rsplit("-",1)[1]
                    print "cname is ", cname, name, powersupplyname, circuit_ps_list, cirlist2


                    while cname in cirlist:
                        print "danger2! already named this circuit!", cname
                        suffix = int(cname.split("-")[2]) + 1
                        newnum2 =  "%02d" % suffix
                        cname = (cname.rsplit("-",1)[0]) + "-" + newnum2
                    print "new name ", cname


                    #only add one circuit device per ps
                    if powersupplyname not in circuit_ps_list:
                        
                        magnetcircuit.add_device(sdict,adict,psdict)
                        circuit_ps_list[powersupplyname] = cname 

                        print "adding circuit name ", magnetcircuit.itemName, cname, circuit_ps_list

                        self.parameters['CircuitProxies'] = [cname]
                        
                    else:
                        #if we aleady made this circuit device, add it to this magnet properties
                        print "!!!ALART!!! already added a circuit device for ", self.itemName
                        


                        self.parameters['CircuitProxies'] = [circuit_ps_list[powersupplyname]]

                        #need to get the name of the circuit device from the ps dict though
                        print "exiting circuit device is", circuit_ps_list[powersupplyname]
                        
                        print "current mags ",  system+"-"+location

                        print "current mags 2",  sdict.servers


                        #current_mags = sdict.servers["%s/%s" % (devclass, system+"-"+location)][devclass][circuit_ps_list[powersupplyname]].properties
                        current_mags = sdict.servers["%s/%s" % ("MagnetCircuit", system+"-"+location)]["MagnetCircuit"][circuit_ps_list[powersupplyname]].properties


                        #for circuits json
                        print "cir name from ps ", circuit_ps_list[powersupplyname], psdict
                        ps_current_mags = psdict.Circuits[circuit_ps_list[powersupplyname]].Properties

                        if name in current_mags['MagnetProxies']:
                            print "circuit already has magnet ", name
                        else:
                            ps_current_mags['MagnetProxies'].append(name)
                            current_mags['MagnetProxies'].append(name)

                        print "magnets on cir ", current_mags['MagnetProxies'], len(current_mags['MagnetProxies'])
                        #need to average the currents, even if already done so in excel (depends on field order)
                        if 'ExcitationCurveFields' in current_mags:

                            assoc_field_m =  current_mags['ExcitationCurveFields']
                            this_field_m  =  fieldsmatrix

                            assoc_curr_m =  current_mags['ExcitationCurveCurrents']
                            this_curr_m  =  currentsmatrix
                            
                            print "field matrix assoc   is ", assoc_field_m
                            print "field matrix current is ", this_field_m

                            print "current matrix assoc   is ", assoc_curr_m
                            print "current matrix current is ", this_curr_m
                            
                            for i in xrange(dim):
                                print i
                                newFields  =  [ ( x*(len(current_mags['MagnetProxies']) -1) + y ) / len(current_mags['MagnetProxies'])  for y,x in zip(this_field_m[i],assoc_field_m[i])]
                                newCurrents = [ ( x*(len(current_mags['MagnetProxies']) -1) + y ) / len(current_mags['MagnetProxies'])  for y,x in zip(this_curr_m[i],assoc_curr_m[i])]

                            print "new fields   ", newFields
                            print "new currents ", newCurrents
                            current_mags['ExcitationCurveFields'][i] = newFields
                            print "updated: ", current_mags['ExcitationCurveFields']
                            current_mags['ExcitationCurveCurrents'][i] = newCurrents
                            print "updated: ", current_mags['ExcitationCurveCurrents']

                        #print "props", current_mags['MagnetProxies']

                        #if already have a circuit device, magnet must have sisters
                        #self.parameters['Sisters'].append('bill')

                
                    #circuitname = name + "circuit"
                    #circuitdevclass = devclass + "circuit"
                    #circuitserver = server+ "circuit"
                    #


                    #self.parameters["PowerSupply"] = [powersupplyname]
                    # self.parameters["Circuit"] = [powersupplyname]
                    #print  item.properties["powersupply"]
            
                else:
                    print "NOT A MAGNET"

                devdict.properties = self.parameters

                #for circuits json
                if "CR" in name:
                    psdevdict.Properties = self.psparameters
                
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
    doCalib=False
    doAlarms=False
    excelName = 'MagnetCalibrationData_fullBC2.xls'
    #excelName = 'MagnetCalibrationData.xls'
    alarmName = 'Magnet_TempInterlock_IMAG_ALARM_140313.xls'

    #configuration
    #update_values = False
    #update_properties = False
    #test_mode = False
    
    # define classes for lattice elements
    types_classes = {}
    types_classes["dip"] = "Magnet"
    types_classes["sbend"] = "Magnet"
    types_classes["sben"] = "Magnet"
    types_classes["rben"] = "Magnet"
    types_classes["csrcsbend"] = "Magnet"
    types_classes["sole"] = "Magnet"
    types_classes["kquad"] = "Magnet"
    types_classes["ksext"] = "Magnet"
    types_classes["hkick"] = "Magnet" 
    types_classes["vkick"] = "Magnet"
    #types_classes["hkick"] = "VACorrector"
    #types_classes["vkick"] = "VACorrector"
    #types_classes["monitor"] = "VABPM"
    #types_classes["watch"] = "VAYAGScreen"
    #types_classes["rfcw"] = "VARfCavity"
    #
    circuit_ps_list = {}

    #read arguments
    for par in sys.argv[1:]:
        if par[0:2] == '--':
            if par == '--calibration-data':
                doCalib = True
            elif par == '--alarm-data':
                doAlarms = True
        #    elif par == '--test-mode':
        #        test_mode = True
        elif inFileName == '':
            inFileName = par
    
    print inFileName, doCalib


    if doAlarms or doCalib:
        import xlrd

    alarm_dict = {}
    if doAlarms:
        print "opening alarms xls"
        xls = xlrd.open_workbook(alarmName)
        sheet = xls.sheet_by_name('Sheet1')
        rows = [sheet.row_values(i) for i in xrange(sheet.nrows)]    
        column_names = rows[0]
        print "cols ", column_names
        for row in enumerate(rows[1:]):    
            if row[1][0]=="":
                continue 
            print row[1][0],row[1][1]
            alarm_dict[row[1][0]] = row[1][1]
        print "DICT IS ", alarm_dict

        #make dict just for alarms! for pyalarm
        json_dict_alarms = SuperDict()
    else:
        json_dict_alarms = None
        
    calib_dict = {}
    
    if doCalib:
        #open excel sheet
        xls = xlrd.open_workbook(excelName)
        sheet = xls.sheet_by_name('linac')
        rows = [sheet.row_values(i) for i in xrange(sheet.nrows)]    
        column_names = rows[7]
        print "cols ", column_names

        for row in enumerate(rows[9:]):  
            print row[1]
            if row[1][2]=="":
                continue
            #this is like 
            #[5.0, u'I.S01A', u'I.S01A.MAG.QE.1', 202005.0, u'#1168-10030-0001', 1.0, -1.0, 2.0, 6.3167, 5.6757, 5.0307500000000003, 4.4208999999999996, 3.8452999999999999, 3.1463999999999999, 2.5179624999999999, 1.8892374999999999, 1.2808725000000001, 0.63988750000000016, 0.0, 0.70470485548532313, 0.63908274382966312, 0.56946571499960408, 0.50203927491440703, 0.43686121069898298, 0.35966476443894108, 0.288993167760146, 0.21848942173091002, 0.14957521795596601, 0.077488874695939805, 0.0052044472873010797, u'T', u'Rotating coil-C1168, #0001.xls', u'https://alfresco.maxlab.lu.se/share/page/site/maxiv/document-details?nodeRef=workspace://SpacesStore/23cdc9d1-a01e-443e-b578-1538637a1472', u'Scanditronix Magnet', 40690.0, '']
            if row[1][2].strip() not in calib_dict:
                if row[1][7] is not "":
                    data_key = int(row[1][7])
                    data_list = row[1][3:33]
                    data_dict = {data_key : data_list}
                    calib_dict[row[1][2].strip()]=data_dict
                #calib_dict[row[1][2]]=row[1][3:33]
            else:
                if row[1][7] is not "":
               #we found more curves for the same magnet 
                    print "found another entry", row[1][2], row[1][7]
                    data_key = int(row[1][7])
                    data_list = row[1][3:33]
                    data_dict = {data_key : data_list}
                    calib_dict[row[1][2].strip()][data_key]=data_list

        print "DICT IS ", calib_dict
        


    # create a parser for the file        
    parser = ElegantLatticeParser(inFileName)     
    
    # parse the file
    parser.parseLatticeFile()
    parser.file.close()
   
    
    # make a json file
    json_dict = SuperDict()
    json_ps =  SuperDict()
    for item in parser.items:

        #PJB hack to deal with magnet circuits here, should really go where other
        #properties set
        #if "CR" in item.itemName and "_" in item.itemName:
        #    magnet,circuit = item.itemName.split("_")
        #    #print "found circuit device magnet", magnet, circuit
        #    # if it is a circuit, add the circuit as a property!
        #    item.properties["circuit"] = circuit
        #if "MAG" in item.itemName:
        #    print "----------------------- found magnet device", item.itemName
        #    # hence also create a magnet circuit device
            

        item.add_device(json_dict,json_dict_alarms, json_ps)
    #print json.dumps(json_dict, indent=4)

    #now we have the dict, loop over again and sort out magnets, power supplies and circuits

    print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ "
    print "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ "
    print json_dict.servers

    outfile = open('magnets.json', 'w')
    json.dump(json_dict, outfile, indent=4)

    if doAlarms:
        outfile2 = open('magnets_alarms.json', 'w')
        json.dump(json_dict_alarms, outfile2, indent=4)

    #!! note that item has parameters, but only want to extract those needed for tango!

    #dump ps circuit info
    outfile3 = open('circuits.json', 'w')
    json.dump(json_ps, outfile3, indent=4)

