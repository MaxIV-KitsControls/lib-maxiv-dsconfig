"""
Routines for reading an Excel file containing server, class and device definitions,
producing a file in the TangoDB JSON format.
"""

from datetime import datetime
import json
import os
import re
import sys
#from traceback import format_exc

from utils import find_device
from appending_dict import AppendingDict
from utils import CaselessDict


MODE_MAPPING = CaselessDict({"ATTR": "DynamicAttributes",
                             "CMD": "DynamicCommands",
                             "STATE": "DynamicStates",
                             "STATUS": "DynamicStatus"})

ATTRIBUTE_PROPERTY_NAMES = ["label", "format",
                            "min_value", "min_alarm", "min_warning",
                            "max_value", "min_alarm", "min_warning",
                            "unit", "polling_period", "change_event",
                            "description", "mode"]
PYALARM_REC = "HTML"
PYALARM_AUTORESET = "60"
PYALARM_MAXMESSAGES = "1"
PYALARM_THRESHOLD ="1"
PYALARM_STARTUPDELAY = "0"

###############################################################################################

def make_py_att_properties(row):
    "Set tag properties of Py Att Processor"

    prop_dict = AppendingDict()

    # Properties column are the tags
    if "Tag" in row:
        prop_dict["tag_list"] = row["tag"]

    return prop_dict

###############################################################################################

def make_eth_ip_properties(row):
    "Set tag properties of ether ip device"

    prop_dict = AppendingDict()

    # Properties column are the tags - here can add a polling period            

    newname = ""
    if "." in row["Tag"]:
        newname = row["Tag"].replace(".","__")

    arg = row["tag"] + ", " + row["Scan period"]

    if newname != "":
        arg = arg + ", " + newname 

    prop_dict["Tags"] = arg

    return prop_dict

###############################################################################################

def make_pyalarm_properties(etherip_dev, origrow, alarms_rows):
    "Set pyalarm properties"

    prop_dict = AppendingDict()

    #look for individual alma and almd tags in other sheet

    added = []
    column_names = alarms_rows[0]
    for i, row_ in enumerate(alarms_rows[1:]):
        # now loop over alarm tags!
        row = CaselessDict(dict((str(name), str(col).strip())
                                for name, col in zip(column_names, row_)
                                if col not in ("", None)))

        if "Tag" not in row: #might be a section divider
            continue

        altype = origrow["Data Type"]

        if row["Tag"].split(".")[0] == origrow["Tag"] and row["Tag"] not in added:

            added.append(row["Tag"])

            newname = row["Tag"].replace(".","__")

            if "InAlarm" in newname:

                severity = "ALARM" #For HH and LL and all ALMD
                if altype=="ALMA":
                    if "_HIn" in newname or "_LIn" in newname:
                        severity = "WARNING"

                condition = ""
                condition = etherip_dev+"/"+newname

                desc =  row["Alarm text"]

                prop_dict["AlarmList"] = newname+":"+condition
                prop_dict["AlarmSeverities"]  = newname+":"+severity
                prop_dict["AlarmDescriptions"]  = newname+":"+desc

    return prop_dict

###############################################################################################

def make_eth_ip_alarm_properties(origrow, alarms_rows):
    "Set tag properties of ether ip device coming from alma/almd block"

    prop_dict = AppendingDict()

    #look for individual alma/almd tags in other sheet
    added = []
    column_names = alarms_rows[0]
    for i, row_ in enumerate(alarms_rows[1:]):
        # now loop over alarm tags!
        row = CaselessDict(dict((str(name), str(col).strip())
                                for name, col in zip(column_names, row_)
                                if col not in ("", None)))

        if "Tag" not in row:
            continue

        if row["Tag"].split(".")[0] == origrow["Tag"] and row["Tag"] not in added:

            added.append(row["Tag"])

            newname = row["Tag"].replace(".","__")
            prop_dict["Tags"] = row["Tag"] + ", " + origrow["Scan period"] + ", " + newname


    return prop_dict

###############################################################################################
def process_achromat_col_name(name):
    if str(name)=="R3" or str(name[0])=="B":
        newname = str(name)
    elif "PLC0" in str(name): #put tags related to plc itself under r3
        newname = "R3"
    else:
        newname = "R3-"+str(name)
    return newname

###############################################################################################

def make_eth_ip_device(plcnum,achromat,plcsystem):
    """
    Return ether ip device name
    """
    #EtherIP device is typically like R-311/VAC/PLC-01
    #In the spreadsheet, achromat may be "R3" for something general, 3xx for an achromat
    #or Bxxx for a beamline
    #domain = process_achromat_col_name(achromat)
    domain = achromat
    family = plcsystem
    member = "PLC-0%i"%plcnum
    return domain+"/"+family+"/"+member

###############################################################################################

def make_pyalarm_device(plcnum,achromat,plcsystem):
    """
    Return pyalarm device name
    """
    #PyAlarm device is typically like R-311/VAC/PLC-01-ALARM
    #The achromat changes and PLC can be 01 or 02, this is always VAC subsystem
    #domain = process_achromat_col_name(achromat)
    domain = achromat
    family = plcsystem
    member = "PLC-0%i-ALARM"%plcnum
    return domain+"/"+family+"/"+member

###############################################################################################

def make_eth_ip_server(achromat):
    #inst = process_achromat_col_name(achromat)
    inst = achromat
    return "%s/%s" % ("AllenBradleyEIP", inst)

###############################################################################################

def make_pyalarm_server(achromat):
    #inst = process_achromat_col_name(achromat)
    inst = achromat
    return "%s/%s" % ("PyAlarm", inst)

###############################################################################################

def make_py_att_device(achromat,subsystem,number):
    """
    Return pyattribute processor device name
    """
    
    #PyAttProc device is like R-311/VAC/TC0-01
    #get "311", "WAT" and "TCO06"
    domain = process_achromat_col_name(achromat)
    family = subsystem
    member = number[:-2] + '-' + number[-2:]
    
    return domain+"/"+family+"/"+member

###############################################################################################

def make_py_att_server(subsystem):
    return "%s/%s" % ("PyAttributeProcessor", subsystem)

###############################################################################################

def convert(plc_config, plctype, plcnum,rows, alarms_rows, definitions, skip=True, dynamic=False, config=False):

    "Update a dict of definitions from data"

    errors = []
    column_names = rows[0]

    already_added_ethip = []
    already_added_pyala = []
    already_added_tags = []

    def handle_error(i, msg):
        if skip:
            errors.append((i, msg))
        else:
            raise

    for i, row_ in enumerate(rows[1:]):

        is_almad = False

        # The plan is to try to find all information on the
        # line, raising exceptions if there are unrecoverable
        # problems. Those are caught and reported.
        
        # Filter out empty columns
        # Note: is just casting col to str OK? What could happen to e.g. floats?
        row = CaselessDict(dict((str(name), str(col).strip())
                                for name, col in zip(column_names, row_)
                                if col not in ("", None)))
        
        # Skip empty lines
        if not row:
            continue

        # Target of the properties; device or class?
        if "Subsystem" in row and "No" in row:

            #shouldn't need such a check:
            if "Tag" not in row:
                continue
            if row["Tag"] in already_added_tags:
                continue
            already_added_tags.append(row["Tag"])   

            achromat = row["Achromat"]

            #rename what is in first column. e.g. add R3 prefix if needed
            #special case for plc01 and 02, get merged into r3
            achromat = process_achromat_col_name(achromat)

            #py_att_device = make_py_att_device(row["Achromat"],row["Subsystem"],row["No"])
            eth_ip_device = make_eth_ip_device(plcnum,achromat,plctype)

            try:
                # full device definition
                #pyatt_srvr = make_py_att_server(row["Subsystem"])
                ethip_srvr = make_eth_ip_server(achromat)
                #pyatt_target = lambda: definitions.servers[pyatt_srvr]["PyAttributeProcessor"][py_att_device]
                ethip_target = lambda: definitions.servers[ethip_srvr]["AllenBradleyEIP"][eth_ip_device]

                #if type is alma there must be alarm tags in other sheet
                if row["Data Type"]=="ALMA" or row["Data Type"]=="ALMD":
                    #make pyalarm device and server
                    pyalarm_device = make_pyalarm_device(plcnum,achromat,plctype)
                    pylarm_srvr = make_pyalarm_server(achromat)
                    pyalarm_target = lambda: definitions.servers[pylarm_srvr]["PyAlarm"][pyalarm_device]
                    is_almad = True

            except KeyError:
                # is the device already defined?
                print "EXCEPTION!!!"
        else:  
            print "ROW NOT PARSED", row

        #put some properties into py att device - everything but alarms
        ###py_att_props = make_py_att_properties(row)
        ###if py_att_props:
        ###    pyatt_target().properties = py_att_props

        #put tags as properties into ether ip device (skip alma and almd ones)
        if not is_almad:
            eth_ip_props = make_eth_ip_properties(row)

        #put alarm tags from other sheet as properties into ether ip device
        if is_almad:
            eth_ip_alarm_props = make_eth_ip_alarm_properties(row, alarms_rows)
            #set pyalarm props, too
            pyalarm_props = make_pyalarm_properties(eth_ip_device, row, alarms_rows)

    
        if not is_almad and eth_ip_props:
            ethip_target().properties = eth_ip_props

            #add one-off properties. This assumes one etherip device for one achromat! (or beamline)
            #achromat here is as written in the sheet, not what becomes domaine or instance
            if achromat not in already_added_ethip:
                already_added_ethip.append(achromat)
                single_prop_dict = {} #not appending!
                single_prop_dict["MinimumScanPeriod"] = plc_config["minscan"]
                single_prop_dict["CPUSlot"] = int(plc_config["slot"])
                single_prop_dict["PLC"] = plc_config["ip"]
                ethip_target().properties = single_prop_dict


        if is_almad and eth_ip_alarm_props:
            ethip_target().properties = eth_ip_alarm_props
            #For pyalarm
            pyalarm_target().properties = pyalarm_props

            #add one-off properties. Some etherip device (achromat) may only have alarms, if achromat is really e.g A11xxxx
            #This assumes one etherip device for one achromat, not very flexible!
            if achromat not in already_added_ethip:
                already_added_ethip.append(achromat)
                single_prop_dict = {} #not appending!
                single_prop_dict["MinimumScanPeriod"] = plc_config["minscan"]
                single_prop_dict["CPUSlot"] = int(plc_config["slot"])
                single_prop_dict["PLC"] = plc_config["ip"]
                ethip_target().properties = single_prop_dict

            #add one-off properties. This assumes one alarm device for one achromat!
            if achromat not in already_added_pyala:
                already_added_pyala.append(achromat)
                single_prop_dict = {}
                single_prop_dict["AutoReset"] = PYALARM_AUTORESET
                single_prop_dict["StartupDelay"] = PYALARM_STARTUPDELAY
                single_prop_dict["AlarmThreshold"] = PYALARM_THRESHOLD
                pyalarm_target().properties = single_prop_dict

    return errors

###############################################################################################

def print_errors(errors):
    if errors:
        print >> sys.stderr, "%d lines skipped" % len(errors)
        for err in errors:
            line, msg = err
            print >> sys.stderr, "%d: %s" % (line + 1, msg)

###############################################################################################

def xls_to_dict(xls_filename, pages=None, skip=False):

    """Make JSON out of an XLS sheet of device definitions."""

    plc_config = {}
    plc1_config = {}
    plc2_config = {}
    plctype = "VAC"
    import xlrd

    xls = xlrd.open_workbook(xls_filename)
    definitions = AppendingDict()

    if not pages:
        pages = xls.sheet_names()


    #read config page first
    sheet = xls.sheet_by_name("Config")
    rows = [sheet.row_values(i) for i in xrange(sheet.nrows)]

    plc1_config["ip"]=rows[1][1]
    plc1_config["slot"]=rows[1][2]
    plc1_config["minscan"]=rows[1][3]
    plc2_config["ip"]=rows[2][1]
    plc2_config["slot"]=rows[2][2]
    plc2_config["minscan"]=rows[2][3]
    print " configs ", plc1_config, plc2_config

    for page in pages:
        print "In page ", page
        if page == "Config":
            continue #we already read this one!

        if "PLC:" not in page:
            continue

        #Specific to PLC tag files
        #Sheets named like "PLC:01,Achromat:301-310,Tags", "PLC:01,Achromat:301-310,Alarms"
        page_l = str(page).split(",")
        plc_num = page_l[0].split(":")[1]
        ach_num = page_l[1].split(":")[1]
        type    = page_l[2]

        print type, plc_num, ach_num
        
        rows_tags   = []
        rows_alarms = []

        if type=="Tags":

            #which plc
            if int(plc_num)==1:
                print "dealing with plc 1"
                plc_config=plc1_config
                print plc_config
            else:
                print "dealing with plc 2"
                plc_config=plc2_config
                print plc_config
            
            sheet = xls.sheet_by_name(page)
            #deduce alarms sheet name
            alarms_page = "PLC:"+plc_num+",Achromat:"+ach_num+",Alarms"
            print "alarms ", alarms_page
            alarms_sheet = xls.sheet_by_name(alarms_page)
            rows = [sheet.row_values(i) for i in xrange(sheet.nrows)]
            alarms_rows = [alarms_sheet.row_values(i) for i in xrange(alarms_sheet.nrows)]
            
            errors = convert(plc_config, plctype, int(plc_num),rows, alarms_rows,definitions, skip=skip)
            print_errors(errors)

    return definitions

###############################################################################################

def get_stats(defs):
    "Calculate some numbers"

    servers = set()
    instances = set()
    classes = set()
    devices = set()

    for srvr_inst, clss in defs.servers.items():
        server, instance = srvr_inst.split("/")
        servers.add(server)
        instances.add(instance)
        for clsname, devs in clss.items():
            classes.add(clsname)
            for devname, dev in devs.items():
                devices.add(devname)

    return {"servers": len(servers), "instances": len(instances),
            "classes": len(classes), "devices": len(devices)}

###############################################################################################

def main():
    from optparse import OptionParser

    usage = "usage: %prog [options] XLS [PAGE1, PAGE2, ...]"
    parser = OptionParser(usage=usage)
    parser.add_option("-t", "--test", action="store_true",
                      dest="test", default=False,
                      help="just test, produce no JSON")
    parser.add_option("-q", "--quiet", action="store_false",
                      dest="verbose", default=True,
                      help="don't print errors to stdout")
    parser.add_option("-f", "--fatal", action="store_false",
                      dest="skip", default=True,
                      help="don't skip, treat any parsing error as fatal")

    options, args = parser.parse_args()
    if len(args) < 1:
        sys.exit("You need to give an XLS file as argument.")
    filename = args[0]
    pages = args[1:]

    data = xls_to_dict(filename, pages, skip=options.skip)
    metadata = dict(
        _title="MAX-IV Tango JSON intermediate format",
        _source=os.path.split(sys.argv[1])[-1],
        _version=1,
        _date=str(datetime.now()))
    data.update(metadata)

    if not options.test:
        #print json.dumps(data, indent=4)
        outfile = open('config.json', 'w')
        json.dump(data, outfile, indent=4)

    stats = get_stats(data)

    print >>sys.stderr, ("\n"
        "Total: %(servers)d servers, %(instances)d instances, "
        "%(classes)d classes and %(devices)d devices defined.") % stats


if __name__ == "__main__":
    main()
