"""Provide functions to parse a callable excel spreadsheets.""" 

# Imports

import xlrd, json, sys, os
from collections import OrderedDict, Mapping
from importlib import import_module
from optparse import OptionParser

# Utils

def special_update(d, u):
    """Update nested dictionnaries while prioritizing the first argument."""
    if not (isinstance(d, Mapping) and isinstance(u, Mapping)):
        return d if d is not None else u
    for k, v in u.iteritems():
        d[k] = special_update(d.get(k), v)
    return d

def max_or_none(*args):
    """Maximum function considering None as a maximum value."""
    return None if None in args else max(*args)

# Excel functions

def get_markup_index(sheet, col, markup):
    """Find a markup in a given column and return the following index."""
    for i,key in enumerate(sheet.col_values(col)):
            if key == markup:
                return i+1
    return None

def get_range_dct(sheet, col, start=0, stop=None, markup=None):
    """Get a value->range dictionnary from a given column."""
    if markup:
        start = max_or_none(start, get_markup_index(sheet, col, markup))
    if start is None:
        return {}
    result = OrderedDict()
    previous_key, previous_start = None, None
    for i,key in enumerate(sheet.col_values(col, start, stop), start):
        if key != "":
            if previous_key is not None:
                result[previous_key] = previous_start, i
            previous_key, previous_start = key, i
    if previous_key is not None:
        result[previous_key] = previous_start, i+1
    return result

# Callable excel functions

def get_kwargs(sheet, start, stop):
    """Get the keywords arguments between two indexes."""
    kwargs = {}
    keyword_dct = get_range_dct(sheet, 2, start, stop)
    for keyword, (start, stop) in keyword_dct.items():
        dct = get_range_dct(sheet, 3, start, stop)
        value = list(dct) if len(dct) > 1 else next(iter(dct))
        try: integer = int(value)
        except (ValueError, TypeError): pass
        else: value = integer if integer==value else value
        kwargs[str(keyword)] = value
    return kwargs
    
def get_call_list(filename):
    """Get the call list from a callable excel spreadsheet."""
    result = []
    with xlrd.open_workbook(filename) as book:
        for sheet in book.sheets():
            package_dct = get_range_dct(sheet, 0, markup="Package")
            for package, (start, stop) in package_dct.items():
                func_dct = get_range_dct(sheet, 1, start, stop)
                for func, (start, stop) in func_dct.items():
                    kwargs = get_kwargs(sheet, start, stop)
                    result.append((package, func, kwargs))
    return result

# Data functions

def process_call_list(lst, skip=False, verbose=True):
    """Process a given call list and return the results."""
    result = []
    errors = ImportError, ValueError, TypeError, AttributeError
    for module_name, func_name, kwargs in lst:
        # Build prototype
        prototype = "{0}.{1}(".format(module_name, func_name)
        for key, value in kwargs.items():
            prototype += '{0}={1}, '.format(key, value)
        if prototype.endswith(' '):
            prototype = prototype[:-2] 
        prototype += ')'
        # Print prototype
        if verbose:
            print "Executing: " + prototype
        # Execute
        try:
            module = import_module(module_name)
            func = getattr(module, func_name)
            value = func(**kwargs)
        # Fail
        except errors as exc:
            if not skip: raise exc
            else: print(exc)
        # Success
        else:
            result.append(value)
    return result

def join_data(lst, source=None):
    """Join a list of json strings or dictionnaries into a single dict."""
    data = {}
    for mapping in lst:
        if isinstance(mapping, basestring):
            mapping = json.loads(mapping)
        special_update(data, mapping)
    if source:
        data['_source'] = source
    return data

# XLS to Dict function

def callable_xls_to_dict(filename, skip=False, verbose=True, to_json=False):
    """Convert a callable excel spreadsheet to a data dictionnary."""
    calls = get_call_list(filename)
    if not calls:
        return
    strings = process_call_list(calls, skip, verbose)
    data = join_data(strings, filename)
    if to_json:
        return json.dumps(data, indent=4, sort_keys=True)
    return data

# Command lines arguments for configuration script

def parse_command_line_args(desc):
    """Parse arguments given in command line"""
    usage = "%prog [-i INPUT] [-o OUTPUT] [-v] [-w]"
    parser = OptionParser(usage=usage, description=desc, version='%prog v1.0')

    msg = "The input callable excel spreadsheet."
    parser.add_option('-i', '--input', metavar='IN',
                      type='str', help=msg, default='')

    msg = "The output tango database json file"
    parser.add_option('-o', '--output', metavar='OUT',
                      type='str', help=msg, default='')
 
    msg = "Display informations"
    parser.add_option('-v', '--verbose', action="store_true", help=msg, default=False)

    msg = "Write the Tango Database"
    parser.add_option('-w', '--write', action="store_true", help=msg, default=False)

    options, _ = parser.parse_args()
    return options.input, options.output, options.write, options.verbose

# Main function for configuration scripts

def main(desc, module_name=None, function=None):
    """Run the script."""
    kwargs = {}
    remove = False
    # Parse command line args
    input_file, output_file, write, verbose = parse_command_line_args(desc)
    # Process input file
    if input_file and module_name and function:
        prototype = ".".join((module_name, function.__name__))
        for module, func, keywords in get_call_list(input_file):
            if module == module_name and func == function.__name__:
                kwargs = keywords
                if verbose:
                    print "'{0}' found".format(prototype)
                    print "kwargs = " + str(kwargs)
                break
        else:
            print "'{0}' not found".format(prototype)
            return
    # Generate json file
    if module_name and function:
        string = function(**kwargs)
    elif input_file:
        string = callable_xls_to_dict(input_file, True, verbose, True)
    else:
        print 'An input file is required.'
        return
    # Display json file
    if verbose:
        print('Json string generated:')
        print(string)
    # Write temporary file
    if output_file == "" and write:
        remove = True
        output_file = "temp.json"
    # Write output file
    if output_file:
        with open(output_file, mode='w') as f:
            f.write(string)
    if verbose:
        print('Exported to: ' + output_file)
    # Write tango database
    if write:
        from dsconfig import configure
        sys.argv = [__name__, output_file, "-w"]
        configure.main()
    # Remove temporary file
    if remove:
        os.remove(output_file)
        if verbose:
            print('Removed: ' + output_file)
    print('OK!') 

# Main execution

if __name__ == "__main__":
    main("Generate a Tango json file for a given callable excel spreadsheet.")

            
    
