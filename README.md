## Dsconfig

This is the JSON based device config system.

*Be very careful when using in production!*

The goal of this project is to provide tools for configuring a Tango database in a convenient way. Right now the focus is on supporting Excel files as input ("xls2json"), but support for other formats should follow.

The main idea is that the input files are parsed and turned into an intermediate JSON format, specified by a schema. This file can then be given to the "json2tango" tool which then tries to make the database contents match, by adding, modifying or removing servers, devices and properties.

The JSON format is easy to create and supported by many tools and languages, so generating them from various sources should be straightforward. Once you have such a file, it should be a simple thing to configure the Tango database.


### JSON format

This is an example of the format, with comments (not actually supported by JSON so don't copy-paste this!):

    {
        // these lines are meta information and are ignored so far
        "_version": 1,
        "_source": "ConfigInjectorDiag.xls",
        "_title": "MAX-IV Tango JSON intermediate format",
        "_date": "2014-11-03 17:45:04.258926",

        // here comes the actual Tango data
        // First, server instances and devices...
        "servers": {
            "some-server/instance": {
                "SomeDeviceClass": {
                    "some/device/1": {
                        "properties": {
                            "someImportantProperty": [
                                "foo",
                                "bar"
                            ],
                            "otherProperty": ["7"]
                        },
                        "attribute_properties": {
                            "anAttribute": {
                                "min_value": ["-5"],
                                "unit": ["mV"]
                            }
                        }
                    }
                }
            }
        },
        // Here you can list your class properties
        "classes": {
            "SomeDeviceClass": {
                "properties": {
                    "aClassProperty": ["67.4"]
                }
            }
        }
    }

Note that all properties are given as lists of strings. This is how the Tango DB represents them so it gets a lot easier to compare things if we do it too.

Note: the format is now more loosely defined; it is allowed to split the server and instance names into separate levels, like so:

    "servers": {
        "some-server": {
            "instance": {
                "SomeDeviceClass": ...

Note: Leaving out "properties" in a device will mean that the tool just ignores any existing properties when applying the configuration. An empty properties object ("properties": {}) means that existing properties will get removed. Same goes for "attribute_properties".


### xls2json

The format supported is almost identical to the dsgenerator format, with a few changes:
 - It is now possible to spread server definitions over any number of pages, and to selectively use only a subset of these by giving their names to the xls2json tool.
 - The column names (the first line of each column) are now significant, so that their order can be relaxed. There are a few differences to the "standard" sheet though; "ServerName" should be "Server", "Devices" should be "Device" and, in the "ParamConfig" tab, "Parameter" should now be "Attribute". These changes were made for consistency.
 - A few features have been added for flexibility; see the example Excel file in "test/files/test.xls".

Converting an excel file is done like this:

    $ xls2json config.xls

This will output the resulting JSON data to stdout. If there are errors or warnings, they will be printed on stderr. To save the JSON to a file, just redirect the output.

By default, all sheets are processed. If you want to only include some of them, include the sheet names as further arguments to the command:

    $ xls2json config.xls sheet1 sheet2

The "Dynamics" and "ParamConfig" sheets are treated specially as they follow a different style. Some syntax checking is done on dynamic formulas, to make sure they compile. Failures are printed to stderr and the corresponding properties skipped, so be careful (see the -f flag to override this).

The command is quite verbose and it will by default happily skip lines that contain incomplete information. Make sure to check the stderr output for hints about this. At the end the command prints a line of statistics, listing the number of servers, etc, it has found. This is intended as a useful sanity check. Also look over the JSON result to see if it makes sense.

Useful flags (see --help):

 * --fatal (-f) means that the command will treat any parsing failure as a fatal error and exit instead of skipping the line as normal. Use if you don't like the lenient default behavior.


### json2tango

This tool reads a JSON file (or from stdout if no filename is given), validates it and (optionally) configures a Tango database accordingly. By default, it will only check the current DB state and print out what actions would be performed, without changing anything. This should always be the first step, in order to catch errors before they are permanently written to the DB.

    $ json2tango config.json

Inspect the output of this command carefully. Lines in red means removal, green additions and yellow changes. Also the old and new values are printed. Note that properties are stored as lists of strings in the DB, so don't be confused by the fact that your numeric properties turn up as strings.

[Pro-tip: if you're unsure of what's going on, it's a good idea to inspect the output of the "-d" argument (see below) before doing any non-trivial changes. It's less readable than the normal diff output but garanteed to be accurate.]

A summary of the numbers of different database operations is printed. This should be useful to double check, usually you should have a good idea of e.g. how many devices should be added, etc.

Once you're convinced that the actions are correct, add the "-w" flag to the command line (this can be at the end or anywhere). Now the command will actually perform the actions in the Tango DB.

For safety and convenience, the program also writes the previous DB state that was changed into a temp JSON file (this is the same as the output of the -d flag). It should be possible to undo the changes made by swapping your input JSON file with the temp file (this is a new feature that is not tested for many cases so don't rely on it.)

Note that the tool in principle only concerns itself with the server instances defined in your JSON file. All other servers in the DB are left untouched. The exception is if your JSON contains devices that already exist in the DB, but in different servers. The devices will be moved to the new servers, and if any of the original servers become empty of devices, they will be removed. There is currently no other way to remove a server with dsconfig.

Some useful flags (see --help for a complete list):

 * --write (-w) is needed in order to actually do anything to the database. This means that the command will perform the actions needed to bring the DB into the described state. If the state is already correct, nothing is done.

 * --update (-u) means that "nothing" (be careful, see caveats below) will be removed, only changed or added. Again the exception is any existing duplicates of your devices. Also, this only applies to whole properties, not individual lines. So if your JSON has lines removed from a property, the lines will be removed from the DB as the whole property is overwritten, regardless of the --update flag.

 * --include (-i) [Experimental] lets you filter the configuration before applying it. You give a filter consisting of a "term" (server/class/device/property) and a regular expression, separated by colon. E.g. "--include=device:VAC/IP.*01". This will cause the command to only apply configuration that concerns those devices matching the regex. It is possible to add several includes, just tack more "--include=..." statements on.

 * --exclude (-x) [Experimental] works like --include except it removes the matching parts from the config instead.


Some less useful flags:

 * --no-validation (-v) skips the JSON validation step. If you know what you're doing, this may be useful as the validation is very strict, while the tool itself is more forgiving. Watch out for unexpected behavior though; you're on your own! It's probably a better idea to fix your JSON.

 * --dbcalls (-d) prints out all the Tango database API calls that were, or would have been, made to perform the changes. This is mostly handy for debugging problems.

 * --sleep (-s) tweaks the time to wait between db calls. The default is 0.01 s. This is intended to lighten the load on the Tango DB service a bit, but it can be set to 0 if you just want the config to be done as fast as possible.
