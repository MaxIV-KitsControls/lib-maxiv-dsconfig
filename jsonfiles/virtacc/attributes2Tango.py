###############################################################################
##     Unlike the regular use of the DsGenerator to create devices and
##     their properties, this script sets the attribute values of the 
##     running virtual accelerator devices, reading from the matr file
###############################################################################


import re
import sys
from deviceServerInfo import *
import PyTango

class attributes2Tango():

    def __init__(self, filename=None):
        self.filename=filename
        self._numOfRows = 0
        self._numOfElements = 0
        self.devDict =  {}

    def readRowsAndElements(self):
        fd = open(self.filename, 'r')
        #fd.next()
        line = fd.readline()
        line = fd.readline()
        self._numOfElements = int(line.split(' ')[2])
        self._numOfRows = self._numOfElements + 2
        fd.close()

    def getNumOfRows(self):
        return self._numOfRows

    def getNumOfElements(self):
        return self._numOfElements

    def getClasses(self):
        self.readRowsAndElements()
        classLines = re.compile(r'^\w+', re.MULTILINE)
        classes = classLines.findall(open(self.filename).read())
        self.classList = classes[2:self._numOfRows]
        return self.classList

    def getAttributes(self):
        pass

    def getDeviceNames(self):
        devNamesLines = re.compile(r'^\w+\s\w.+', re.MULTILINE)
        lines = devNamesLines.findall(open(self.filename).read())
        for line in lines[2:13]:
            self.devNamesList.append(line.split(' ')[1])
        return self.devNamesList

    def renameDeviceName(self, name):
        result = None
        words = name.split('.')
        if len(words) == 3:
            result = '/'.join(map(str, words))
        elif len(words) == 4:
            result = "%s.%s/%s/%s" % (words[0], words[1], words[2], words[3])
        elif len(words) == 5:
            result = "%s.%s/%s/%s.%s" % (words[0], words[1], words[2],
                                         words[3], words[4]
                                         )

        return result
        # This should work with the naming convention if '.' replace only the separator
        #return name[::-1].replace('.','/',2)[::-1]

    def parseClassAndName(self, line):
        words=line.split(" ")
         #print words

        if len(words)<2:
            return None

        else:
            elegant_type = words[0]
            device_name =  words[1]

            if device_name in ("W-INIT", "W-ACHR1A"):
                return None
            elif elegant_type in ("KQUAD","WATCH","HKICK","VKICK","CSRCSBEND","KSEXT"):
                return elegant_type, device_name
            else:
                return None

    def populateDeviceDict(self):
        f = open(self.filename, 'r')
        lastDsName = None
        for line in f.readlines():

             #print line 

            result=None
            if not line.startswith('    '):
                result = self.parseClassAndName(line)

                if result is not None:
                    lastDsName = result[1]
                    print "device ", result 
                    self.devDict[lastDsName] = DeviceServerInfo(result[0], result[0],  result[1])

            else:
                if lastDsName is not None:
                    words=line.split("=")  
                    prop= words[0].strip()
                    val =  words[1].strip()
                    print lastDsName, prop, val

                    self.devDict[lastDsName].properties[prop]=val

                        
        f.close()
        return self.devDict

    def filter_attributes(self):

        print "in filtering"
        name_parsing_string='(?P<system>[a-zA-Z0-9]+)\.(?P<location>[a-zA-Z0-9]+)\.(?P<subsystem>[a-zA-Z0-9]+)\.(?P<device>[a-zA-Z0-9]+)\.(?P<num>[0-9]+)'
        pattern = re.compile(name_parsing_string)  


        for device in devDict:

            print devDict[device].name
            name_items = pattern.search(devDict[device].name)
            system = name_items.group('system')
            subsystem = name_items.group('subsystem')
            location = name_items.group('location')
            dev = name_items.group('device')
            num = name_items.group('num')
            if num == None: num = ''
            name = (system+"."+location + '/' + subsystem + '/' + dev + num).encode('ascii', 'ignore')
            name = name.split("_")[0]    #fix for circuit devices with an underscore, shouldn't be needed 
            #I.BC1.MAG.QB.1 needs to be like I.BC1/MAG/QB1
            devDict[device].name = name

            if devDict[device].match_attributes() is False:
                print  devDict[device].name, "not is list"
                continue

            print "-------- final name", devDict[device].name

            # write to DB
            proxy = PyTango.DeviceProxy(devDict[device].name)
            for eachProp in devDict[device].properties:

                #get rid of unitd
                devDict[device].properties[eachProp] =  devDict[device].properties[eachProp].split(" ")[0]

                print " --------------------- ", eachProp, devDict[device].properties[eachProp]

                proxy.write_attribute(eachProp,devDict[device].properties[eachProp])


if __name__ == '__main__':

    for par in sys.argv[1:]:
        inFileName = par


    lat = attributes2Tango(inFileName)
    devDict = lat.populateDeviceDict()
    #pfor device in devDict:
        #pprint devDict[device].name
        #print devDict[device].className
        #print devDict[device].serverInst
        #print devDict[device].name
        #pfor eachProp in devDict[device].properties:
         #p   print eachProp, devDict[device].properties[eachProp]
        #    print type(devDict[device].properties)

    lat.filter_attributes()
    #lat.write_attributes_to_db()

    print len(devDict.keys())
