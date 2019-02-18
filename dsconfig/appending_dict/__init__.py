from collections import defaultdict, Mapping
from .caseless import CaselessDictionary


class SetterDict(CaselessDictionary, defaultdict):
    """
    A recursive defaultdict with extra bells & whistles

    It enables you to set keys at any depth without first creating the
    intermediate levels, e.g.

      d = SetterDict()
      d["a"]["b"]["c"] = 1

    It also allows access using normal getattr syntax, interchangeably:

      d.a["b"].c == d.a.b.c == d["a"]["b"]["c"]

    Note: only allows string keys for now.

    Keys are caseless, meaning that the key "MyKey" is the same as
    "mykey", "MYKEY", etc. The case

    Note: this thing is dangerous! Accessing a non-existing key will
    result in creating it, which means that confusing behavior is
    likely. Please use it carefully and convert to an ordinary dict
    (using to_dict()) when you're done creating it.
    """

    def __init__(self, value={}, factory=None):
        factory = factory or SetterDict
        self.__dict__["_factory"] = factory
        CaselessDictionary.__init__(self)
        defaultdict.__init__(self, factory)
        for k, v in list(value.items()):
            self[k] = v

    def __getitem__(self, key):
        try:
            return CaselessDictionary.__getitem__(self, key)
        except KeyError:
            return self.__missing__(key)

    def __setitem__(self, key, value):
        if isinstance(value, SetterDict):
            CaselessDictionary.__setitem__(self, key, value)
        elif isinstance(value, Mapping):
            CaselessDictionary.__setitem__(self, key, self._factory(value))
        else:
            CaselessDictionary.__setitem__(self, key, value)

    def __getattr__(self, name):
        return self.__getitem__(name)

    def __setattr__(self, key, value):
        return self.__setitem__(key, value)

    def __repr__(self):
        return self.to_dict().__repr__()

    def __eq__(self, other):
        return self.to_dict() == other

    def __ne__(self, other):
        return self.to_dict() != other

    def to_dict(self):
        """Returns a ordinary dict version of itself"""
        result = {}
        for key, value in list(self.items()):
            if isinstance(value, SetterDict):
                result[key] = value.to_dict()
            else:
                result[key] = value
        return result


def merge(d, u):
    "Recursively 'merge' a Mapping into another"
    for k, v in u.items():
        if isinstance(v, Mapping):
            if k in d:
                merge(d[k], v)
            else:
                d[k] = v
        elif isinstance(d, Mapping):
            d[k] = u[k]


def list_of_strings(value):
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    else:
        return [str(value)]


class AppendingDict(SetterDict):

    """An extra weird SetterDict where assignment adds items instead of
    overwriting. It also allows setting nested values using dicts (or
    any Mapping). Scalar values are converted into lists of strings.

    Plus of course the features of SetterDict.

    !!!Attention!!!  This is pretty dangerous. It is only intended for
    cases where you need to do a lot of updating and don't want the
    hassle of creating a million recursive dicts. It will silently
    convert things and it will create any paths that are accessed
    (even without writing), etc. It is very risky to use it like a
    normal dict. Always convert it to a dict using to_dict() when
    you're done changing it! You can always create an AppendingDict
    from it again if needed later.

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
        SetterDict.__init__(self, value, AppendingDict)

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
