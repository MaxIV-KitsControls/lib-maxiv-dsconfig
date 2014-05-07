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


def add_device(sdict, inst, dev, al_name, al_cond, al_desc, al_sev, al_rec):
    print inst, dev, al_name, al_cond, al_desc, al_sev, al_rec
    devdict = sdict.servers["PyAlarm"]["PyAlarm/"+inst]["PyAlarm"][dev]
    if "AlarmList" not in devdict.properties:
        devdict.properties["AlarmList"] = []
    devdict.properties["AlarmList"].append(al_name+":"+al_cond)
    if "AlarmDescriptions" not in devdict.properties:
        devdict.properties["AlarmDescriptions"] = []
    devdict.properties["AlarmDescriptions"].append(al_name+":"+al_desc)
    if "AlarmSeverities" not in devdict.properties:
        devdict.properties["AlarmSeverities"] = []
    devdict.properties["AlarmSeverities"].append(al_name+":"+al_sev)
    if "AlarmReceivers" not in devdict.properties:
        devdict.properties["AlarmReceivers"] = []
    devdict.properties["AlarmReceivers"].append(al_name+":"+al_rec)

def xls_to_dict(xls_filename):
    json_dict = SuperDict()
    xls = xlrd.open_workbook(xls_filename)
    sheet = xls.sheet_by_name("Alarms")
    for line in xrange(1, sheet.nrows):
        # above skips row 0 (col headers)
        # look at all rows but only read those with entry in first col
        if sheet.row_values(line)[0] is not "":
            print "IN LINE ", line, sheet.row_values(line)[0] 
            dev_config = sheet.row_values(line)
            add_device(json_dict, *dev_config[:7])
    return json_dict

def main():
    import sys
    data = xls_to_dict(sys.argv[1])
    print json.dumps(data, indent=4)

if __name__ == "__main__":
    main()



