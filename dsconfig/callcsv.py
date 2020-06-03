"""Provide functions to parse a callable csv file."""

# Imports

import os
import sys
import csv
import json
from collections import Mapping
from importlib import import_module
from optparse import OptionParser


# Utils

def special_update(d, u):
    """Update nested dictionnaries while prioritizing the first argument."""
    if not (isinstance(d, Mapping) and isinstance(u, Mapping)):
        return d if d is not None else u
    for k, v in u.items():
        d[k] = special_update(d.get(k), v)
    return d


def max_or_none(*args):
    """Maximum function considering None as a maximum value."""
    return None if None in args else max(*args)


def cast_list(lst):
    """Convert a list of a string to the corresponding value."""
    result = []
    for value in lst:
        # Integer conversion
        try:
            value = int(value)
        except (ValueError, TypeError):
            # Float conversion
            try:
                value = float(value)
            except (ValueError, TypeError):
                # Hexa conversion
                try:
                    value = int(value, 16)
                except (ValueError, TypeError):
                    # Ignore
                    pass
        # Append
        result.append(value)
    # Return
    if not result:
        return ""
    if len(result) == 1:
        return result[0]
    return tuple(result)


# Csv functions

def get_column(matrix, col, start=None, stop=None, step=None):
    """Get the column of a matrix, with optional range arguments."""
    return [row[col] for row in matrix][slice(start, stop, step)]


def get_markup_index(matrix, col, markup):
    """Find a markup in a given column and return the following index."""
    for i, key in enumerate(get_column(matrix, col)):
            if key == markup:
                return i+1
    return None


def get_range_lst(matrix, col, start=0, stop=None, markup=None):
    """Get a value->range dictionnary from a given column."""
    if markup:
        start = max_or_none(start, get_markup_index(matrix, col, markup))
    if start is None:
        return {}
    result = []
    previous_key, previous_start = None, None
    for i, key in enumerate(get_column(matrix, col, start, stop), start):
        if key != "":
            if previous_key is not None:
                result.append((previous_key, previous_start, i))
            previous_key, previous_start = key, i
    if previous_key is not None:
        result.append((previous_key, previous_start, i+1))
    return result


# Callable csv functions

def get_kwargs(matrix, start, stop):
    """Get the keywords arguments between two indexes."""
    kwargs = {}
    keyword_lst = get_range_lst(matrix, 2, start, stop)
    for keyword, start, stop in keyword_lst:
        lst = get_range_lst(matrix, 3, start, stop)
        values = [key for key, _, _ in lst]
        kwargs[str(keyword)] = cast_list(values)
    return kwargs


def get_call_list(filename):
    """Get the call list from a callable cls file."""
    result = []
    with open(filename) as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        matrix = [[value.strip() for value in row] for row in reader]
    package_lst = get_range_lst(matrix, 0, markup="Package")
    # Process
    result = []
    for package, start, stop in package_lst:
        func_lst = get_range_lst(matrix, 1, start, stop)
        for func, start, stop in func_lst:
            kwargs = get_kwargs(matrix, start, stop)
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
        for key, value in list(kwargs.items()):
            prototype += '{0}={1}, '.format(key, value)
        if prototype.endswith(' '):
            prototype = prototype[:-2]
        prototype += ')'
        # Print prototype
        if verbose:
            print("Executing: " + prototype)
        # Execute
        try:
            module = import_module(module_name)
            func = getattr(module, func_name)
            value = func(**kwargs)
        # Fail
        except errors as exc:
            if not skip:
                raise exc
            else:
                print(exc)
        # Success
        else:
            result.append(value)
    return result


def join_data(lst, source=None):
    """Join a list of json strings or dictionnaries into a single dict."""
    data = {}
    for mapping in lst:
        if isinstance(mapping, str):
            mapping = json.loads(mapping)
        special_update(data, mapping)
    if source:
        data['_source'] = source
    return data


# CSV to Dict function

def callable_csv_to_dict(filename, skip=False, verbose=True, to_json=False):
    """Convert a callable csv file to a data dictionnary."""
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

    msg = "The input callable csv file"
    parser.add_option('-i', '--input', metavar='IN',
                      type='str', help=msg, default='')

    msg = "The output tango database json file"
    parser.add_option('-o', '--output', metavar='OUT',
                      type='str', help=msg, default='')

    msg = "Display informations"
    parser.add_option('-v', '--verbose',
                      action="store_true", help=msg, default=False)

    msg = "Write the Tango Database"
    parser.add_option('-w', '--write',
                      action="store_true", help=msg, default=False)

    options, args = parser.parse_args()

    if args:
        msg = "No argument expected, options only.\n"
        msg += "Use --help for further information."
        parser.error(msg)

    return options.input, options.output, options.write, options.verbose


# Main function for configuration scripts

def main(desc=None, module_name=None, function=None):
    """Run the script."""
    kwargs = {}
    remove = False
    desc = desc or "Generate a Tango json file for a given callable csv file."
    # Parse command line args
    input_file, output_file, write, verbose = parse_command_line_args(desc)
    # Process input file
    if input_file and module_name and function:
        prototype = ".".join((module_name, function.__name__))
        for module, func, keywords in get_call_list(input_file):
            if module == module_name and func == function.__name__:
                kwargs = keywords
                if verbose:
                    print(("'{0}' found".format(prototype)))
                    print(("kwargs = " + str(kwargs)))
                break
        else:
            msg = "'{0}' not found in {1}"
            print(msg.format(prototype, get_call_list(input_file)))
            return
    # Generate json file
    if module_name and function:
        if not input_file and verbose:
            msg = 'No input file given. '
            msg += 'Default configuration will be used'
            print(msg)
        data = function(**kwargs)
        if isinstance(data, Mapping):
            string = json.dumps(data, indent=4, sort_keys=True)
        elif isinstance(data, str):
            string = data
        else:
            msg = "The function didn't return a valid data format.\n"
            msg += "The type is {0} instead.".format(type(data))
            print(msg)
            print(data)
            return
    elif input_file:
        string = callable_csv_to_dict(input_file, True, verbose, True)
    else:
        print('An input file is required.')
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
    if verbose and output_file:
        print(('Exported to: ' + output_file))
    # Write tango database
    if write:
        from dsconfig import configure
        sys.argv = [__name__, output_file, "-w"]
        configure.main()
    # Remove temporary file
    if remove:
        os.remove(output_file)
        if verbose:
            print(('Removed: ' + output_file))
    print('OK!')


# Main execution

if __name__ == "__main__":
    main()
