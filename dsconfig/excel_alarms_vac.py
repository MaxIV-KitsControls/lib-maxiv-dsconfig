from collections import defaultdict
import json

import xlrd


class SuperDict(defaultdict):
    "A recursive defaultdict with extra bells & whistles"

    def __init__(self):
        defaultdict.__init__(self, SuperDict)

    def __setattr__(self, attr, value):
        self[attr] = value

    def __getattr__(self, attr):
        return self[attr]


def add_device(sdict, inst, dev, al_name, al_cond, al_desc):
    print inst, dev, al_name, al_cond, al_desc
    # devdict = sdict.servers["PyAlarm"]["PyAlarm/"+inst]["PyAlarm"][dev]
    devdict = sdict.servers["PyAlarm/"+inst]["PyAlarm"][dev]
    if "AlarmList" not in devdict.properties:
        devdict.properties["AlarmList"] = []
    devdict.properties["AlarmList"].append(al_name+":"+al_cond)
    if "AlarmDescriptions" not in devdict.properties:
        devdict.properties["AlarmDescriptions"] = []
    devdict.properties["AlarmDescriptions"].append(al_name+":"+al_desc)
    #hard code severity and some other things - only one per instance
    if "AlarmSeverities" not in devdict.properties:
        devdict.properties["AlarmSeverities"] = []
    devdict.properties["AlarmSeverities"].append(al_name+":ALARM")
    if "AlarmReceivers" not in devdict.properties:
        devdict.properties["AlarmReceivers"] = []
    devdict.properties["AlarmReceivers"].append(al_name+":HTML")
    #hard code severity and some other things - only one per instance
    if "AlarmThreshold" not in devdict.properties:
        devdict.properties["AlarmThreshold"] = []
    devdict.properties["AlarmThreshold"]  = [1]
    if "LogFile" not in devdict.properties:
        devdict.properties["LogFile"] = []
    devdict.properties["LogFile"]= ["/tmp/pjb/log"]
    if "HtmlFolder" not in devdict.properties:
        devdict.properties["HtmlFolder"] = []
    devdict.properties["HtmlFolder"] = ["/tmp/pjb"]
    if "PollingPeriod" not in devdict.properties:
        devdict.properties["PollingPeriod"] = []
    devdict.properties["PollingPeriod"] = [3]
    if "MaxMessagesPerAlarm" not in devdict.properties:
        devdict.properties["MaxMessagesPerAlarm"] = []
    devdict.properties["MaxMessagesPerAlarm"]= [1]
    if "AutoReset" not in devdict.properties:
        devdict.properties["AutoReset"] = []
    devdict.properties["AutoReset"]= [0]
    if "StartupDelay" not in devdict.properties:
        devdict.properties["StartupDelay"] = []
    devdict.properties["StartupDelay"]= [0]

def xls_to_dict(xls_filename):
    json_dict = SuperDict()
    xls = xlrd.open_workbook(xls_filename)
    sheet = xls.sheet_by_name("Alarms")
    last_server=""
    last_device=""
    last_name=""
    summary_condition=""
    for line in xrange(1, sheet.nrows):
        # above skips row 0 (col headers)
        # look at all rows but only read those with entry in first col
        if sheet.row_values(line)[0] is not "":
            print "IN LINE ", line, sheet.row_values(line)[0] 
            #assume that if you get to a new device, it means a new section of vacuum
            #in this case, need to make a final alarm which is or of all others
            dev_config = sheet.row_values(line)
            print dev_config, dev_config[3].rsplit("/",1)[0] 
            if dev_config[1] != last_device or dev_config[0]=="end":
                print "START NEW SECTION", dev_config[1]
                print "---- ADDING TO JSON summary ", summary_condition, last_name
                if summary_condition!="":
                    add_device(json_dict,last_server,last_device,last_name.rsplit("_",1)[0],summary_condition,"at least one vac. interlock in section %s" %last_name.rsplit("_",2)[0])
                last_server = dev_config[0]
                last_device = dev_config[1]
                last_name = dev_config[2]
                summary_condition=""
            if summary_condition == "":
                summary_condition = summary_condition + dev_config[3]
            else:
                summary_condition = summary_condition + " or " + dev_config[3]

            if dev_config[0]!="end":
                add_device(json_dict, *dev_config[:5])

    return json_dict

def main():
    import sys
    data = xls_to_dict(sys.argv[1])
    #print json.dumps(data, indent=4)
    outfile = open('alarms_vac.json', 'w')
    json.dump(data, outfile, indent=4)

if __name__ == "__main__":
    main()



