import unittest

from appending import SetterDict, AppendingDict


class SetterDictTestCase(unittest.TestCase):

    def test_init_tiny(self):
        TINY_DICT = {"a": 1}
        sd = SetterDict(TINY_DICT)
        self.assertDictEqual(sd, TINY_DICT)

    def test_init_flat(self):
        FLAT_DICT = {"a": 1, "b": 2, "c": 3}
        sd = SetterDict(FLAT_DICT)
        self.assertDictEqual(sd, FLAT_DICT)

    def test_init_nested(self):
        NESTED_DICT = {"a": {"b": 2}}
        sd = SetterDict(NESTED_DICT)
        self.assertDictEqual(sd, NESTED_DICT)

    def test_init_blended(self):
        BLENDED_DICT = {"a": 1, "b": {"c": 3}}
        sd = SetterDict(BLENDED_DICT)
        self.assertDictEqual(sd, BLENDED_DICT)

    def test_init_deep(self):
        DEEP_DICT = {"a": {"b": {"c": {"d": 4}}}}
        sd = SetterDict(DEEP_DICT)
        self.assertDictEqual(sd, DEEP_DICT)

    def test_init_deep(self):
        COMPLEX_DICT = {"a": {"b": {"c": {"d": 4}}}, "e": 5}
        sd = SetterDict(COMPLEX_DICT)
        self.assertDictEqual(sd, COMPLEX_DICT)

    def test_setting(self):
        sd = SetterDict()
        sd["foo"] = 1
        self.assertDictEqual(sd, {"foo": 1})

    def test_setting_nested(self):
        sd = SetterDict()
        sd["foo"]["bar"] = 2
        self.assertDictEqual(sd, {"foo": {"bar": 2}})

    def test_setting_nested_nonempty(self):
        sd = SetterDict({"a": 1})
        sd["foo"]["bar"] = 2
        self.assertDictEqual(sd, {"a": 1, "foo": {"bar": 2}})

    def test_setting_attr(self):
        sd = SetterDict({"a": 1})
        sd.a = 2
        self.assertDictEqual(sd, {"a": 2})

    def test_setting_attr_deep(self):
        sd = SetterDict()
        sd.a.b.c = 4
        self.assertDictEqual(sd, {"a": {"b": {"c": 4}}})


class AppendingDictTestCase(unittest.TestCase):

    def test_basic_appending(self):
        ad = AppendingDict()
        ad.a = 1
        self.assertDictEqual(ad, {"a": ['1']})
        ad.a = 2
        self.assertDictEqual(ad, {"a": ['1', '2']})

    def test_deep_appending(self):
        ad = AppendingDict()
        ad.a.b.c = 1
        ad.a.b.c = 2
        self.assertDictEqual(ad, {"a": {"b": {"c": ['1', '2']}}})

    def test_initial_setting_with_dict(self):
        ad = AppendingDict()
        ad.a = {"b": {"c": 1}}
        self.assertDictEqual(ad, {"a": {"b": {"c": ["1"]}}})

    def test_deep_setting_with_dict(self):
        ad = AppendingDict()
        ad.a.b.c = 1
        ad.a = {"b": {"d": 2}}
        self.assertDictEqual(ad, {"a": {"b": {"c": ['1'], "d": ['2']}}})

    def test_setting_with_sequence(self):
        ad = AppendingDict()
        ad.a = [1, "b"]
        self.assertDictEqual(ad, {"a": ['1', 'b']})

    def test_setting_existing_key_with_sequence(self):
        ad = AppendingDict()
        ad.a = [1, "b"]
        ad.a = [2, "c"]
        self.assertDictEqual(ad, {"a": ['1', 'b', '2', 'c']})

    def test_error_setting_existing_subtree_with_scalar(self):
        ad = AppendingDict()
        ad.a.b.c = 1

        def set_subtree():
            ad.a = 2
        self.assertRaises(ValueError, set_subtree)

    def test_setting_with_appendingdict(self):
        ad = AppendingDict()
        ad2 = AppendingDict({"b": 3, "c": {"d": 4}})
        ad.a.e = 1
        ad.a = ad2
        self.assertDictEqual(
            ad, {"a": {"b": ["3"], "c": {"d": ["4"]}, "e": ["1"]}})

    def test_updating_does_not_work(self):
        "Have not yet implemented this"
        ad = AppendingDict()
        d = {"a": 1, "b": {"c": 3}}
        self.assertRaises(NotImplementedError, ad.update(d))

    def test_set_string_value(self):
        ad = AppendingDict()
        ad.a = "abc"
        self.assertDictEqual(ad, {"a": ["abc"]})
