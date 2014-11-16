from collections import defaultdict, Mapping, Sequence
import json


class SetterDict(defaultdict):
    """
    A recursive defaultdict with extra bells & whistles

    It enables you to set keys at any depth without first creating the
    intermediate levels, e.g.

      d = SetterDict()
      d["a"]["b"]["c"] = 1

    It also allows access using normal getattr syntax, interchangeably:

      d.a["b"].c == d.a.b.c == d["a"]["b"]["c"]

    Note: only allows string keys for now.
    """

    def __init__(self, value={}, factory=None, leaf_conv=None):
        factory = factory or SetterDict
        defaultdict.__init__(self, factory)
        for k, v in value.items():
            if isinstance(v, Mapping):
                SetterDict.__setitem__(self, k, factory(v))
            else:
                if leaf_conv:
                    v = leaf_conv(v)
                SetterDict.__setitem__(self, k, v)

    def __setattr__(self, attr, value):
        self[attr] = value

    def __getattr__(self, attr):
        return self[attr]

    def __repr__(self):
        return json.dumps(self)

    def to_dict(self):
        result = {}
        for key, value in self.items():
            if isinstance(value, SetterDict):
                result[key] = value.to_dict()
            else:
                result[key] = value
        return result


def merge(d, u):
    "Recursively 'merge' a Mapping into another"
    for k, v in u.iteritems():
        if isinstance(v, Mapping):
            merge(d[k], v)
        elif isinstance(d, Mapping):
            d[k] = u[k]


def list_of_strings(value):
    if isinstance(value, list):  # handle e.g. tuple too?
        return [str(v) for v in value]
    else:
        return [str(value)]


class AppendingDict(SetterDict):

    """
    An extra weird SetterDict where assignment adds items instead of
    overwriting. It also allows setting nested values using dicts (or
    any Mapping). Scalar values are converted into lists of strings.

    Plus of course the features of SetterDict.

    a = AppendingDict()
    a.b = 1
    a.b
    -> ['1']
    a.b = 2
    a.b
    -> ['1', '2']

    a = AppendingDict()
    a.b.c.d = 3
    a.b = {"c": {"d": ['3']}}
    a
    -> {"b": {"c": {"d": ['3', '4']}}}

    """

    def __init__(self, value={}):
        SetterDict.__init__(self, value, AppendingDict, list_of_strings)

    def _set(self, attr, value):
        SetterDict.__setitem__(self, attr, value)

    def __setitem__(self, attr, value):
        # I apologize for this method :(
        if attr in self:
            if isinstance(self[attr], AppendingDict):
                if isinstance(value, Mapping):
                    merge(self[attr], value)
                else:
                    raise ValueError("Can't overwrite a subtree "
                                     "with a scalar value.")
            else:
                self[attr].extend(list_of_strings(value))
        else:
            if isinstance(value, Mapping):
                if isinstance(value, AppendingDict):
                    self._set(attr, value)
                else:
                    self._set(attr, AppendingDict(value))
            else:
                self._set(attr, list_of_strings(value))
