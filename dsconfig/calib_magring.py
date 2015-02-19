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

###############################################################################################

def make_magnet_server(magname):
    inst = magname.split("/")[0][:-2]
    print "---------making server name ", inst
    return "%s/%s" % ("Magnet", inst)


def make_circuit_server(magname):
    inst = magname.split("/")[0][:-2]
    print "---------making server name ", inst
    return "%s/%s" % ("MagnetCircuit", inst)


def make_magnet_properties(magnet, polarity, orient):
    "Set magnet properties"

    prop_dict = AppendingDict()
    prop_dict["Polarity"] = polarity
    prop_dict["Orientation"] = orient
    return prop_dict

def make_circuit_properties(circuit, currents, fields):
    "Set circuit properties"

    prop_dict = AppendingDict()
    prop_dict["ExcitationCurveCurrents"] = currents
    prop_dict["ExcitationCurveFields"] = fields
    return prop_dict


###############################################################################################

def convert(rows, magnets, definitions, skip=True, dynamic=False, config=False):

    "Update a dict of definitions from data"

    #print magnets

    errors = []
    column_names = rows[7]

    already_added_ethip = []

    def handle_error(i, msg):
        if skip:
            errors.append((i, msg))
        else:
            raise

    calib_dict = {}
    for row in enumerate(rows[9:]):  
        #print row[1]
        if row[1][2]=="":
            continue

        if row[1][2].strip() not in calib_dict:
            if row[1][7] is not "":
                data_key = int(row[1][7])
                data_list = row[1][3:48]
                data_dict = {data_key : data_list}
                calib_dict[row[1][2].strip()]=data_dict
                #calib_dict[row[1][2]]=row[1][3:33]
        else:
            if row[1][7] is not "":
                #we found more curves for the same magnet 
                #print "found another entry", row[1][2], row[1][7]
                data_key = int(row[1][7])
                data_list = row[1][3:48]
                data_dict = {data_key : data_list}
                calib_dict[row[1][2].strip()][data_key]=data_list
                
    #print "DICT IS ", calib_dict
    #now have dict where key is magnet name and value is a dict of which 
    #key is field order and content is values
    #iterate over the dict now

    for magnet in calib_dict:
        print "Dealing with magnet: ", magnet

        dim = max(calib_dict[magnet].keys(), key=int)
        #print "--- max order is", dim

        fieldsmatrix = [[0 for x in xrange(19)] for x in xrange(dim)] 
        currentsmatrix = [[0 for x in xrange(19)] for x in xrange(dim)] 

        for data in calib_dict[magnet]:
            
            #print '--- ', data, 'corresponds to', calib_dict[magnet][data]

            currents = calib_dict[magnet][data][5:25]
            fields   = calib_dict[magnet][data][25:45]
            #print '--- ',currents, fields

            fieldsmatrix[data-1]=fields
            currentsmatrix[data-1]=currents
            polarity = calib_dict[magnet][data][3]
            orientation = calib_dict[magnet][data][2]
            
        #print '--- ',fieldsmatrix
        #print '--- ',currentsmatrix     

        #now trim the matrices (lists)
        maxlength = 20
        for i,val in enumerate(fieldsmatrix[dim-1]):
            if val=='':
                #print "here ", i , val
                maxlength = i
                break
        #print maxlength
        for i in xrange(dim):
            #print i
            del fieldsmatrix[i][maxlength:]
            del currentsmatrix[i][maxlength:]

        print 'Polarity: ',polarity
        print 'Orientation ',orientation
        print 'Fields:   ',fieldsmatrix
        print 'Currents  ',currentsmatrix
        print "Circuit ", magnets[magnet]

        #now create device in json and add properties
        magnet_device = magnet
        magnet_srvr = make_magnet_server(magnet)
        magnet_target = lambda: definitions.servers[magnet_srvr]["Magnet"][magnet_device]

        circuit_device = magnets[magnet]
        circuit_srvr = make_circuit_server(magnets[magnet])
        circuit_target = lambda: definitions.servers[circuit_srvr]["MagnetCircuit"][circuit_device]

        magnet_props = make_magnet_properties(magnet,polarity,orientation)
        magnet_target().properties = magnet_props

        circuit_props = make_circuit_properties(magnets[magnet],currentsmatrix,fieldsmatrix)
        circuit_target().properties = circuit_props


    return errors

###############################################################################################

def print_errors(errors):
    if errors:
        print >> sys.stderr, "%d lines skipped" % len(errors)
        for err in errors:
            line, msg = err
            print >> sys.stderr, "%d: %s" % (line + 1, msg)

###############################################################################################

def xls_to_dict(xls_filename, fname2, skip=False):

    """Make JSON out of an XLS sheet of device definitions."""

    import xlrd


    #get circuit info from master sheet
    magnets = {}
    xls2 = xlrd.open_workbook(fname2)
    sheet = xls2.sheet_by_name("input_data")
    for i in xrange(sheet.nrows):
        row = sheet.row_values(i)
        if row[0].startswith("I-"):
            magnets[str(row[0]).strip()] = str(row[1].strip())

    xls = xlrd.open_workbook(xls_filename)
    definitions = AppendingDict()

    pages = xls.sheet_names()

    for page in pages:
        print "In page ", page

        sheet = xls.sheet_by_name(page)
        rows = [sheet.row_values(i) for i in xrange(sheet.nrows)]

        errors = convert(rows, magnets, definitions, skip=skip)
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
    fname2 = args[1:][0]

    print "files: ", filename, fname2
    data = xls_to_dict(filename,fname2, skip=options.skip)
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
