import json
import sys

from jsonschema import Draft4Validator, validate, exceptions

from utils import decode_dict


if __name__ == "__main__":
    data_filename, schema_filename = sys.argv[1], sys.argv[2]

    print "Validating '%s' against schema '%s'..." % (data_filename, schema_filename),

    with open(data_filename) as data_json:
        data = json.load(data_json, object_hook=decode_dict)

    with open(schema_filename) as schema_json:
        schema = json.load(schema_json)

    try:
        validate(data, schema)
    except exceptions.ValidationError as e:
        print "data does not match schema:"
        print e
        sys.exit(1)
    else:
        print "success!"
