#!/usr/bin/env python
# 	"$Name:  $";
# 	"$Header:  $";
# =============================================================================
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


class SuperDict(defaultdict):
    "A recursive defaultdict with extra bells & whistles"

    def __init__(self):
        defaultdict.__init__(self, SuperDict)

    def __setattr__(self, attr, value):
        self[attr] = value

    def __getattr__(self, attr):
        return self[attr]


class LatticeFileItem:
    """ """
    itemName = ""
    itemType = ''
    parameters = {}
    properties = {}
    alpars = {}

    def __init__(self, _line=''):
        """
        Construct an object parsing a _line from a lattice file
        """
        self.psparameters = {}
        self.parameters = {}
        self.properties = {}

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
                param_name = ''
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

    def handle_circuit_name(self, itemName, endnum):

        endname = ""
        # hack for bc1
        if "QD" in itemName and "BC1" in itemName:
            endname = "CRQM-" + endnum
            #
            # hack for bc2
        elif "QF" in itemName and "BC2" in itemName and "3" not in itemName and "4" not in itemName and "5" not in itemName:
            endname = "CRQM-" + endnum
        elif "QF" in itemName and "BC2" in itemName and ("3" in itemName or "5" in itemName):
            endname = "CRQ1-01"
        elif "QF" in itemName and "BC2" in itemName and "4" in itemName:
            endname = "CRQ2-01"
            #
        elif "Q" in itemName:
            endname = "CRQ-" + endnum
        elif "CO" in itemName and "X" in itemName:
            endname = "CRCOX-" + endnum
        elif "CO" in itemName and "Y" in itemName:
            endname = "CRCOY-" + endnum
        elif "DI" in itemName:
            endname = "CRDI-" + endnum
            print("dealing with endname  ", endname)
        elif "SX" in itemName:
            endname = "CRSX-" + endnum
        elif "SOL" in itemName:
            endname = "CRSOL-" + endnum
        elif "SM" in itemName:
            endname = "CRSM-" + endnum
        else:
            sys.exit("Cannot convert circuit name" + itemName)

        if "/" in endname:  # in case did not end with number, endname will be some */*/ by mistake
            endname = endname.split("-")[0] + "-01"

        return endname

    def config_alarms(self, pyalarm, alname, alsev, aldesc, pyattname, key):

        alrec = alname + ":" + "HTML"

        if "AlarmList" not in self.alpars[pyalarm]:
            self.alpars[pyalarm]["AlarmList"] = []
        self.alpars[pyalarm]['AlarmList'].append(alname + ":" + pyattname + "/" + key)

        if "AlarmSeverities" not in self.alpars[pyalarm]:
            self.alpars[pyalarm]["AlarmSeverities"] = []
        self.alpars[pyalarm]['AlarmSeverities'].append(alsev)

        if "AlarmDescriptions" not in self.alpars[pyalarm]:
            self.alpars[pyalarm]["AlarmDescriptions"] = []
        self.alpars[pyalarm]['AlarmDescriptions'].append(aldesc)

        if "AlarmReceivers" not in self.alpars[pyalarm]:
            self.alpars[pyalarm]["AlarmReceivers"] = []
        self.alpars[pyalarm]['AlarmReceivers'].append(alrec)

        if "StartupDelay" not in self.alpars[pyalarm]:
            self.alpars[pyalarm]["StartupDelay"] = ["0"]

        if "AutoReset" not in self.alpars[pyalarm]:
            self.alpars[pyalarm]["AutoReset"] = ["60"]

        if "MaxMessagesPerAlarm" not in self.alpars[pyalarm]:
            self.alpars[pyalarm]["MaxMessagesPerAlarm"] = ["1"]

        if "PollingPeriod" not in self.alpars[pyalarm]:
            self.alpars[pyalarm]["PollingPeriod"] = ["5"]

        if "LogFile" not in self.alpars[pyalarm]:
            self.alpars[pyalarm]["LogFile"] = ["/tmp/pjb/log"]

        if "HtmlFolder" not in self.alpars[pyalarm]:
            self.alpars[pyalarm]["HtmlFolder"] = ["/tmp/pjb"]

        if "AlarmThreshold" not in self.alpars[pyalarm]:
            self.alpars[pyalarm]["AlarmThreshold"] = ["1"]

    def match_properties(self):

        devclass = types_classes[self.itemType]

        if "CIR" in self.itemName:
            print("dealing with magnet circuit")

        # for given item type, look up required attributes and properties of tango
        elif devclass in TANGO_PROPERTIES:

            fixed_properties_l = list(TANGO_PROPERTIES[devclass][0].keys())
            # print "fixed tango properties are ", fixed_properties_l

            # add the fixed properties
            self.parameters.update(TANGO_PROPERTIES[devclass][0])

            lattice_properties_l = list(TANGO_PROPERTIES[devclass][1].keys())
            # print "possible lattice tango properties are ", lattice_properties_l
            for k in list(self.parameters.keys()):
                # print "pjb zzz 1", self.parameters["Tilt"], self.parameters
                # print "key", k
                # if not a required property or attribue then pop it
                if k.lower() not in lattice_properties_l and k not in fixed_properties_l:
                    # print "popping ", k
                    self.parameters.pop(k)

                # otherwise rename key if an attribute
                if k.lower() in lattice_properties_l:
                    # print "KEY ", k.lower(), TANGO_PROPERTIES[devclass][1][k.lower()], self.parameters[k]
                    self.parameters[TANGO_PROPERTIES[devclass][1][k.lower()]] = [self.parameters.pop(k)]
                    # print "pjb zzz", self.parameters["Tilt"], self.parameters


        else:
            for k in list(self.parameters.keys()):
                self.parameters.pop(k)

        if "MAG" in self.itemName and not "CIR" in self.itemName:
            self.parameters["Type"] = [self.itemType]

        #
        if "Tilt" in self.parameters:
            if "0.5 pi" in str(self.parameters["Tilt"]):
                self.parameters["Tilt"] = ["90"]
            else:
                self.parameters["Tilt"] = ["0"]
        print("pjbyyy", self.parameters)

    def add_device(self, sdict, adict, psdict,
                   name_parsing_string='(?P<system>[a-zA-Z0-9]+)\.(?P<location>[a-zA-Z0-9]+)\.(?P<subsystem>[a-zA-Z0-9]+)\.(?P<device>[a-zA-Z0-9]+)\.(?P<num>[0-9]+)'):
        """
        Updates json file
        """
        # prepare pattern for parsing name
        pattern = re.compile(name_parsing_string)

        print("In add device for item: " + self.itemName + " as " + self.itemType, self.alpars)
        # only when we know class for certain element 

        print("adict is ", adict)
        circuit_alarm_params = []

        # for case with no final number like I.TR1.MAG.DIE (no .1 etc at end)
        alt_name_parsing_string = '(?P<system>[a-zA-Z0-9]+)\.(?P<location>[a-zA-Z0-9]+)\.(?P<subsystem>[a-zA-Z0-9]+)\.(?P<device>[a-zA-Z0-9]+)'
        alt_pattern = re.compile(alt_name_parsing_string)

        # self.alpars = {}
        devdictalarm = None

        if self.itemType in types_classes:

            print("")
            print("")

            # split name
            name_items = pattern.search(self.itemName)
            parsed = False
            tryagain = False
            if name_items == None:
                print("Warning: Item name in lattice file doesn't match the naming convention.", self.itemName)
                tryagain = True
            else:
                parsed = True
            if tryagain:
                name_items = alt_pattern.search(self.itemName)
                if name_items == None:
                    print("Warning: Item name in lattice file STILL doesn't match the naming convention.",
                          self.itemName)
                else:
                    parsed = True
            if parsed:
                system = name_items.group('system')
                subsystem = name_items.group('subsystem')
                location = name_items.group('location')
                device = name_items.group('device')

                if tryagain == False:
                    num = name_items.group('num')
                else:
                    num = ""

                if num == None: num = ''

                if num != "":
                    num2 = "%02d" % int(num)
                else:
                    num2 = "01"

                self.match_properties()
                print("pjbxxx ", self.parameters)

                # create device for json output
                name = (system + "-" + location + '/' + subsystem + '/' + device + "-" + num2).encode('ascii', 'ignore')
                devclass = types_classes[self.itemType].encode('ascii', 'ignore')
                server = devclass + '/' + system + "-" + location

                # hack for circuits
                if "CIR" in self.itemName:
                    print("orig name", self.itemName, name)

                    # quad circuits named like CRQ
                    # correctors like CRCOX and CRCOY
                    # dipoles like CRDI
                    # solenoid like CRSOL
                    # sextu like CRX
                    endname = name.rsplit("/", 1)[1]

                    # fix circuit names
                    endname = self.handle_circuit_name(self.itemName, num2)
                    name = name.rsplit("/", 1)[0] + "/" + endname

                    # e.g in G00 have COIX 1, 2, 3 and COHX 1 and 2, which would make COX 1, 2, 3 with COIX 1 and 2 being lost!
                    # increment number till unique
                    while name in cirlist:
                        print("danger! already named this circuit!", self.itemName, name)
                        suffix = int(name.split("-")[2]) + 1
                        newnum2 = "%02d" % suffix
                        print(newnum2)
                        name = (name.rsplit("-", 1)[0]) + "-" + newnum2
                        print(name)
                    print("new name ", name)
                    cirlist.append(name)
                    print(cirlist)
                    devclass = "MagnetCircuit"

                    # compact name is to find tag in plc alarms
                    name_l_cir = self.itemName.split(".")
                    section_cir = name_l_cir[1]
                    mid = name_l_cir[3]
                    if "_" in mid:
                        mid = mid.split("_")[0]
                    # hack for SM1A and SM1B in TR1, also DIE, DIF on circuit DI (DIC, DID on TR3)
                    compactnamecir = "_" + name_l_cir[1] + mid + "_"
                    compactnamecir = compactnamecir.replace("1A", "1")
                    compactnamecir = compactnamecir.replace("1B", "1")
                    if "DIE" in compactnamecir:
                        compactnamecir = compactnamecir.replace("DIE", "DI")
                    if "DIF" in compactnamecir:
                        compactnamecir = compactnamecir.replace("DIF", "DI")
                    if "DIC" in compactnamecir:
                        compactnamecir = compactnamecir.replace("DIC", "DI")
                    if "DID" in compactnamecir:
                        compactnamecir = compactnamecir.replace("DID", "DI")

                    print("circuit compact name is ", compactnamecir, name_l_cir)

                    # fill alarm info for circuits
                    #
                    pyalarm = system + "-" + location + '/MAG/ALARM'
                    if adict is not None:
                        devdictalarm = adict.servers["%s/%s" % ("PyAlarm", "I-MAG")]["PyAlarm"][pyalarm]

                        print("init devdictalarm circuit")

                    already_added = ["B_I_SP02DIPBD_DIA_TSW1_A",
                                     "B_I_SP02DIPBD_DIA_TSW2_A"]  # can use this to ignore to. e.g. SP02DIPDB doesnt end in a number but isn't a circuit!
                    for key in alarm_dict:
                        # compact name is like _TR1QF_ but some tags are like _TR1QF2_5_
                        # if compactnamecir in key:
                        if (key not in already_added and compactnamecir in key) or (
                                compactnamecir[:-1] in key and key.count(
                            "_") > 5 and key not in already_added and "F" + num + "_" in key):

                            print("key is", num, key)

                            already_added.append(key)

                            print("FOUND ALARM INFO FOR CIR", compactnamecir, key, alarm_dict[key], section_cir)
                            pyattname = "I-" + section_cir + "/DIA/COOLING"

                            # for the magnets json file
                            circuit_alarm_params = [pyattname, key, alarm_dict[key]]

                            # for the alarms json file
                            alname = 'TemperatureInterlock' + key.split('_')[
                                -2] + '_' + system + "_" + location + '__' + endname.replace("-", "_")
                            alsev = alname + ":" + "ALARM"
                            alrec = alname + ":" + "HTML"
                            aldesc = alname + ":One magnet in circuit " + alarm_dict[key]

                            if pyalarm not in self.alpars:
                                self.alpars[pyalarm] = {}
                            self.config_alarms(pyalarm, alname, alsev, aldesc, pyattname, key)  # will fill self.alpars

                print(
                    "+++++++++++++++++ Creating device server : " + server + " for " + devclass + " (name= " + name + ")")
                print("+++++++++ With properties : ", self.parameters)

                # Dont actually write attributes to DB, only properties
                # see if this class exists and append if so, or create
                devdict = sdict.servers["%s/%s" % (devclass, system + "-" + location)][devclass][name]

                # for circuit json only
                if "CR" in name:
                    psdevdict = psdict.Circuits[name]

                if "MAG" in self.itemName and "CIR" not in self.itemName:

                    # compact name is to find tag in plc alarms
                    name_l = self.itemName.split(".")
                    section = name_l[1]
                    del name_l[0]
                    del name_l[1]
                    # del name_l[2]
                    print("pjb kkk", name_l)
                    compactfullname = "".join(name_l)
                    compactname = compactfullname.split("_")[0]
                    compactname_nonum = compactfullname.split("_")[0][:-1] + "_"

                    print("-------------------- magnet not circuit", self.itemName, compactname)

                    # see what is the ps of the magnet
                    if name in POWER_SUPPLY_MAP:
                        powersupplyname = POWER_SUPPLY_MAP[name]
                    else:
                        print("magnet not in PS map, skipping", name)
                        return

                        # !!!!!!!!!!! *********** create circuit device for each new ps ************!!!!!!!!!!!!
                    #                 copy the magnet and call recursively add device!
                    magnetcircuit = copy.deepcopy(self)
                    magnetcircuit.itemName = self.itemName + ".CIR"

                    magnetcircuit.parameters = {}
                    magnetcircuit.parameters['PowerSupplyProxy'] = [powersupplyname]
                    magnetcircuit.parameters['MagnetProxies'] = [name]
                    magnetcircuit.parameters['RiseTime'] = ["0.0"]
                    magnetcircuit.parameters['ResistanceReference'] = ["0.0"]
                    magnetcircuit.parameters['CoilNames'] = [""]

                    # for the ps json file only
                    magnetcircuit.psparameters['PowerSupplyProxy'] = [powersupplyname]
                    magnetcircuit.psparameters['MagnetProxies'] = [name]

                    # get alarm info from excel
                    pyalarm = system + "-" + location + '/MAG/ALARM'

                    print("adict is again", adict)
                    if adict is not None:
                        devdictalarm = adict.servers["%s/%s" % ("PyAlarm", "I-MAG")]["PyAlarm"][pyalarm]
                        print("init devdictalarm")

                    # set alarms in magnet.json file and in alarms json file  
                    for key in alarm_dict:
                        if compactname in key and key.count("_") < 6:
                            # if compactname in key:

                            pyattname = "I-" + section + "/DIA/COOLING"

                            print("FOUND ALARM INFO FOR ", compactname, key, alarm_dict[key], pyattname, adict)

                            # for the magnets json file
                            if 'TemperatureInterlock' not in self.parameters:
                                self.parameters['TemperatureInterlock'] = [
                                    pyattname + "," + key + "," + alarm_dict[key]]
                            else:
                                self.parameters['TemperatureInterlock'].append(
                                    pyattname + "," + key + "," + alarm_dict[key])

                            # for the alarms json file
                            alname = 'TemperatureInterlock' + key.split('_')[
                                -2] + '_' + system + "_" + location + '__' + 'MAG' + '__' + device + "_" + num2
                            alsev = alname + ":" + "ALARM"
                            aldesc = alname + ":Magnet " + alarm_dict[key]

                            if pyalarm not in self.alpars:
                                self.alpars[pyalarm] = {}
                            self.config_alarms(pyalarm, alname, alsev, aldesc, pyattname, key)  # will fill self.alpars

                            devdictalarm.properties = self.alpars[pyalarm]

                    # set alarms in magnet.json file for all magnets in circuit
                    for key in alarm_dict:
                        if compactname_nonum in key or (compactname[:-1] in key and key.count("_") > 5 and (
                                "F" + num + "_" in key or "_" + num + "_" in key)):
                            # if compactname_nonum in key:
                            print("mag key ", key, compactname_nonum, compactname, "F" + num + "_", "_" + num + "_")
                            pyattname = "I-" + section + "/DIA/COOLING"

                            print("FOUND MORE ALARM INFO FOR ", compactname, key, alarm_dict[key], pyattname, adict)

                            # for the magnets json file
                            if 'TemperatureInterlock' not in self.parameters:
                                self.parameters['TemperatureInterlock'] = [
                                    pyattname + "," + key + "," + alarm_dict[key]]
                            else:
                                self.parameters['TemperatureInterlock'].append(
                                    pyattname + "," + key + "," + alarm_dict[key])

                    polarity = 1
                    orientation = 1

                    # get calibration info from the excel
                    if self.itemName.split("_")[0] in calib_dict:
                        print("FOUND CALIB INFO", self.itemName)
                        # find max multipole expansions
                        dim = max(list(calib_dict[self.itemName.split("_")[0]].keys()), key=int)

                        print("--- max order is", dim)

                        # create arrays of this dimensions, other dimension is 11

                        fieldsmatrix = [[0 for x in range(19)] for x in range(dim)]
                        # print fieldsmatrix
                        currentsmatrix = [[0 for x in range(19)] for x in range(dim)]

                        # iterate over keys and add to the array
                        for key in calib_dict[self.itemName.split("_")[0]]:
                            print('--- ', key, 'corresponds to', calib_dict[self.itemName.split("_")[0]][key])
                            currents = calib_dict[self.itemName.split("_")[0]][key][5:25]
                            fields = calib_dict[self.itemName.split("_")[0]][key][25:45]
                            print('--- ', currents, fields)

                            fieldsmatrix[key - 1] = fields
                            currentsmatrix[key - 1] = currents
                            # key here is the multipole order. any one should have same polarity
                            polarity = calib_dict[self.itemName.split("_")[0]][key][3]
                            orientation = calib_dict[self.itemName.split("_")[0]][key][2]
                            # print "P, O", polarity, orientation

                        print('--- ', fieldsmatrix)
                        print('--- ', currentsmatrix)

                        # now trim the matrices (lists)
                        maxlength = 20
                        for i, val in enumerate(fieldsmatrix[dim - 1]):
                            if val == '':
                                print(i, val)
                                maxlength = i
                                break
                        print(maxlength)
                        for i in range(dim):
                            print(i)
                            del fieldsmatrix[i][maxlength:]
                            del currentsmatrix[i][maxlength:]

                        print('Now--- ', fieldsmatrix)
                        print('Now--- ', currentsmatrix)

                        magnetcircuit.parameters['ExcitationCurveCurrents'] = currentsmatrix
                        magnetcircuit.parameters['ExcitationCurveFields'] = fieldsmatrix

                    self.parameters['Orientation'] = [str(int(orientation))]
                    self.parameters['Polarity'] = [str(int(polarity))]

                    # assign circuit name as property of magnet device
                    # no regex to fix name here so do by hand
                    # e.g. I.BC1.MAG.COEX.4.CIR -> I-BC1/MAG/COEX-CIR-04

                    cname = name.rsplit("/CIR", 1)[0]
                    endname = cname.rsplit("/", 1)[1]
                    endnum = cname.rsplit("-", 1)[1]
                    endname = self.handle_circuit_name(self.itemName, endnum)
                    cname = cname.rsplit("/", 1)[0] + "/" + endname

                    print("cname is ", cname, name, powersupplyname, circuit_ps_list)

                    while cname in cirlist:
                        print("danger2! already named this circuit!", cname)
                        suffix = int(cname.split("-")[2]) + 1
                        newnum2 = "%02d" % suffix
                        cname = (cname.rsplit("-", 1)[0]) + "-" + newnum2
                    print("new name ", cname)

                    # only add one circuit device per ps
                    if powersupplyname not in circuit_ps_list:

                        magnetcircuit.add_device(sdict, adict, psdict)
                        circuit_ps_list[powersupplyname] = cname

                        print("adding circuit name ", magnetcircuit.itemName, cname, circuit_ps_list)
                        self.parameters['CircuitProxies'] = [cname]

                    else:
                        # if we aleady made this circuit device, add it to this magnet properties
                        print("!!!ALART!!! already added a circuit device for ", self.itemName, name, system, location)

                        if system == "R3":
                            system = "I"
                        if location == "301L":
                            location = "TR3"

                        self.parameters['CircuitProxies'] = [circuit_ps_list[powersupplyname]]

                        # need to get the name of the circuit device from the ps dict though
                        print("exiting circuit device is", circuit_ps_list[powersupplyname])

                        # print "current mags ",  system+"-"+location
                        # print "current mags 2",  sdict.servers

                        current_mags = \
                            sdict.servers["%s/%s" % ("MagnetCircuit", system + "-" + location)]["MagnetCircuit"][
                                circuit_ps_list[powersupplyname]].properties
                        # for circuits json
                        print("cir name from ps ", circuit_ps_list[powersupplyname], psdict)
                        ps_current_mags = psdict.Circuits[circuit_ps_list[powersupplyname]].Properties
                        print("current mags ", current_mags['MagnetProxies'])
                        if name in current_mags['MagnetProxies']:
                            print("circuit already has magnet ", name)
                        else:
                            ps_current_mags['MagnetProxies'].append(name)
                            current_mags['MagnetProxies'].append(name)

                        print("magnets on cir ", current_mags['ExcitationCurveFields'], current_mags['MagnetProxies'],
                              len(current_mags['MagnetProxies']))
                        # need to average the currents, even if already done so in excel (depends on field order)
                        if 'ExcitationCurveFields' in current_mags:

                            assoc_field_m = current_mags['ExcitationCurveFields']
                            this_field_m = fieldsmatrix

                            assoc_curr_m = current_mags['ExcitationCurveCurrents']
                            this_curr_m = currentsmatrix

                            print("field matrix assoc   is ", assoc_field_m)
                            print("field matrix current is ", this_field_m)

                            print("current matrix assoc   is ", assoc_curr_m)
                            print("current matrix current is ", this_curr_m)

                            for i in range(dim):
                                print(i)

                                # fix for CRSM take abs field values since opp sign
                                if circuit_ps_list[powersupplyname] in ["I-TR3/MAG/CRSM-01", "I-TR3/MAG/CRDI-01"]:
                                    newFields = [(abs(x) * (len(current_mags['MagnetProxies']) - 1) + abs(y)) / len(
                                        current_mags['MagnetProxies']) for y, x in
                                                 zip(this_field_m[i], assoc_field_m[i])]
                                else:
                                    newFields = [(x * (len(current_mags['MagnetProxies']) - 1) + y) / len(
                                        current_mags['MagnetProxies']) for y, x in
                                                 zip(this_field_m[i], assoc_field_m[i])]

                                newCurrents = [(x * (len(current_mags['MagnetProxies']) - 1) + y) / len(
                                    current_mags['MagnetProxies']) for y, x in zip(this_curr_m[i], assoc_curr_m[i])]

                            print("new fields   ", newFields)
                            print("new currents ", newCurrents)
                            current_mags['ExcitationCurveFields'][i] = newFields
                            print("updated: ", current_mags['ExcitationCurveFields'])
                            current_mags['ExcitationCurveCurrents'][i] = newCurrents
                            print("updated: ", current_mags['ExcitationCurveCurrents'])


                else:
                    print("NOT A MAGNET")

                devdict.properties = self.parameters

                # for circuits json
                if "CR" in name:
                    psdevdict.Properties = self.psparameters


class ElegantLatticeParser:
    """ Class for parsing an elegant lattice file. """
    fileName = ""
    file = None
    items = []

    def __init__(self, _fileName):
        """Constructs a parser object.

        Keyword arguments:
        _fileName -- the name of file to be parsed        
        """
        self.fileName = _fileName
        self.file = io.open(_fileName)

    def parseLatticeFile(self):
        """ """
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
    doCalib = False
    doAlarms = False
    excelName = 'MagnetCalibrationData.xls'
    alarmName = 'IMAG_ALARM_140923_Magnets.xls'

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
    # types_classes["hkick"] = "VACorrector"
    # types_classes["vkick"] = "VACorrector"
    # types_classes["monitor"] = "VABPM"
    # types_classes["watch"] = "VAYAGScreen"
    # types_classes["rfcw"] = "VARfCavity"
    #
    circuit_ps_list = {}
    # circuit_alarm_params = None

    # read arguments
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

    print(inFileName, doCalib)

    if doAlarms or doCalib:
        import xlrd

    alarm_dict = {}
    if doAlarms:
        print("opening alarms xls")
        xls = xlrd.open_workbook(alarmName)
        sheet = xls.sheet_by_name('Sheet1')
        rows = [sheet.row_values(i) for i in range(sheet.nrows)]
        column_names = rows[0]
        print("cols ", column_names)
        for row in enumerate(rows[1:]):
            if row[1][0] == "":
                continue
            print(row[1][0], row[1][1])
            alarm_dict[row[1][0]] = row[1][1]
        print("DICT IS ", alarm_dict)

        # make dict just for alarms! for pyalarm
        json_dict_alarms = SuperDict()
    else:
        json_dict_alarms = None

    calib_dict = {}

    if doCalib:
        # open excel sheet
        xls = xlrd.open_workbook(excelName)

        for name in ["linac", "transfer 1,5 GeV", "transfer 3 GeV", "thermionic gun"]:

            # sheet = xls.sheet_by_name('Linac')
            sheet = xls.sheet_by_name(name)
            rows = [sheet.row_values(i) for i in range(sheet.nrows)]
            column_names = rows[7]
            print("cols ", column_names)

            for row in enumerate(rows[9:]):
                print(row[1])
                if row[1][2] == "":
                    continue
                # this is like 
                # [5.0, u'I.S01A', u'I.S01A.MAG.QE.1', 202005.0, u'#1168-10030-0001', 1.0, -1.0, 2.0, 6.3167, 5.6757, 5.0307500000000003, 4.4208999999999996, 3.8452999999999999, 3.1463999999999999, 2.5179624999999999, 1.8892374999999999, 1.2808725000000001, 0.63988750000000016, 0.0, 0.70470485548532313, 0.63908274382966312, 0.56946571499960408, 0.50203927491440703, 0.43686121069898298, 0.35966476443894108, 0.288993167760146, 0.21848942173091002, 0.14957521795596601, 0.077488874695939805, 0.0052044472873010797, u'T', u'Rotating coil-C1168, #0001.xls', u'https://alfresco.maxlab.lu.se/share/page/site/maxiv/document-details?nodeRef=workspace://SpacesStore/23cdc9d1-a01e-443e-b578-1538637a1472', u'Scanditronix Magnet', 40690.0, '']
                if row[1][2].strip() not in calib_dict:
                    if row[1][7] is not "":
                        data_key = int(row[1][7])
                        data_list = row[1][3:48]
                        data_dict = {data_key: data_list}
                        calib_dict[row[1][2].strip()] = data_dict
                    # calib_dict[row[1][2]]=row[1][3:33]
                else:
                    if row[1][7] is not "":
                        # we found more curves for the same magnet 
                        print("found another entry", row[1][2], row[1][7])
                        data_key = int(row[1][7])
                        data_list = row[1][3:48]
                        data_dict = {data_key: data_list}
                        calib_dict[row[1][2].strip()][data_key] = data_list

        print("DICT IS ", calib_dict)

    # create a parser for the file        
    parser = ElegantLatticeParser(inFileName)

    # parse the file
    parser.parseLatticeFile()
    parser.file.close()

    # make a json file
    json_dict = SuperDict()
    json_ps = SuperDict()
    for item in parser.items:
        item.add_device(json_dict, json_dict_alarms, json_ps)
    # print json.dumps(json_dict, indent=4)

    # now we have the dict, loop over again and sort out magnets, power supplies and circuits

    print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ ")
    print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ ")
    print(json_dict.servers)

    outfile = open('magnets.json', 'w')

    # have final json dict here
    print("THE FINAL DICT")
    topl = list(json_dict['servers'].keys())
    for item in topl:
        if "Circuit" in item:
            # print json_dict['servers'][item]
            for cir in json_dict['servers'][item]:
                # print json_dict['servers'][item][cir]['ExcitationCurveCurrents']
                # print json_dict['servers'][item]["MagnetCircuit"]
                for c in json_dict['servers'][item]["MagnetCircuit"]:
                    for key in json_dict['servers'][item]["MagnetCircuit"][c]["properties"]:
                        if key == "ExcitationCurveCurrents":
                            ls = json_dict['servers'][item]["MagnetCircuit"][c]["properties"][key]
                            print(key, [str(x) for x in ls])
                            json_dict['servers'][item]["MagnetCircuit"][c]["properties"][key] = [str(x) for x in ls]
                        if key == "ExcitationCurveFields":
                            ls = json_dict['servers'][item]["MagnetCircuit"][c]["properties"][key]
                            print(key, [str(x) for x in ls])
                            json_dict['servers'][item]["MagnetCircuit"][c]["properties"][key] = [str(x) for x in ls]

    json.dump(json_dict, outfile, indent=4)

    if doAlarms:
        outfile2 = open('magnets_alarms.json', 'w')
        json.dump(json_dict_alarms, outfile2, indent=4)

    # !! note that item has parameters, but only want to extract those needed for tango!

    # dump ps circuit info
    outfile3 = open('circuits.json', 'w')
    json.dump(json_ps, outfile3, indent=4)
