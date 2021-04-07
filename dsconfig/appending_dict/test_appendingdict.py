try:
    import unittest2 as unittest
except:
    import unittest

from . import SetterDict, AppendingDict, merge


class MergeTestCase(unittest.TestCase):

    def test_merge(self):
        a = {1: 2, 3: 4}
        b = {5: 6}
        merge(a, b)
        self.assertEqual(a, {1: 2, 3: 4, 5: 6})

    def test_merge_mapping(self):
        a = {1: 2}
        b = {3: {4: 5}}
        merge(a, b)
        self.assertEqual(a, {1: 2, 3: {4: 5}})


class SetterDictTestCase(unittest.TestCase):

    def test_init_tiny(self):
        TINY_DICT = {"a": 1}
        sd = SetterDict(TINY_DICT)
        self.assertDictEqual(sd.to_dict(), TINY_DICT)

    def test_init_flat(self):
        FLAT_DICT = {"a": 1, "b": 2, "c": 3}
        sd = SetterDict(FLAT_DICT)
        self.assertDictEqual(sd.to_dict(), FLAT_DICT)

    def test_init_nested(self):
        NESTED_DICT = {"a": {"b": 2}}
        sd = SetterDict(NESTED_DICT)
        self.assertDictEqual(sd.to_dict(), NESTED_DICT)

    def test_init_blended(self):
        BLENDED_DICT = {"a": 1, "b": {"c": 3}}
        sd = SetterDict(BLENDED_DICT)
        self.assertDictEqual(sd.to_dict(), BLENDED_DICT)

    def test_init_deep(self):
        DEEP_DICT = {"a": {"b": {"c": {"d": 4}}}}
        sd = SetterDict(DEEP_DICT)
        self.assertDictEqual(sd.to_dict(), DEEP_DICT)

    def test_init_deep(self):
        COMPLEX_DICT = {"a": {"b": {"c": {"d": 4}}}, "e": 5}
        sd = SetterDict(COMPLEX_DICT)
        self.assertDictEqual(sd.to_dict(), COMPLEX_DICT)

    def test_setting(self):
        sd = SetterDict()
        sd["foo"] = 1
        self.assertDictEqual(sd.to_dict(), {"foo": 1})

    def test_setting_nested(self):
        sd = SetterDict()
        sd["foo"]["bar"] = 2
        self.assertDictEqual(sd.to_dict(), {"foo": {"bar": 2}})

    def test_setting_nested_nonempty(self):
        sd = SetterDict({"a": 1})
        sd["foo"]["bar"] = 2
        self.assertDictEqual(sd.to_dict(), {"a": 1, "foo": {"bar": 2}})

    def test_setting_attr(self):
        sd = SetterDict({"a": 1})
        sd.a = 2
        self.assertDictEqual(sd.to_dict(), {"a": 2})

    def test_setting_attr_deep(self):
        sd = SetterDict()
        sd.a.b.c = 4
        self.assertDictEqual(sd.to_dict(), {"a": {"b": {"c": 4}}})

    def test_to_dict(self):
        orig = {"a": {"b": ["3"], "c": {"d": ["4"]}, "e": ["1"]}}
        sd = SetterDict(orig)
        d = sd.to_dict()
        self.assertDictEqual(orig, d)

    def test_keys_case_insensitive(self):
        sd = SetterDict()
        sd.a.B.c = 1
        self.assertEqual(sd.A.b.C, sd.a.b.c, 1)

    def test_keeps_original_key_case(self):
        sd = SetterDict()
        sd.FoO = 1
        sd.foo = 2
        sd.baR = 3
        sd.BAR = 4
        self.assertListEqual(list(sd.keys()), ["FoO", "baR"])


class AppendingDictTestCase(unittest.TestCase):

    def test_basic_appending(self):
        ad = AppendingDict()
        ad["a"] = 1
        self.assertDictEqual(ad.to_dict(), {"a": ['1']})
        ad["a"] = 2
        self.assertDictEqual(ad.to_dict(), {"a": ['1', '2']})

    def test_deep_appending(self):
        ad = AppendingDict()
        ad["a"]["b"]["c"] = 1
        ad["a"]["b"]["c"] = 2
        print((type(ad["a"]["b"])))
        self.assertDictEqual(ad.to_dict(), {"a": {"b": {"c": ['1', '2']}}})

    def test_initial_setting_with_dict(self):
        ad = AppendingDict()
        ad.a = {"b": {"c": 1}}
        self.assertDictEqual(ad.to_dict(), {"a": {"b": {"c": ["1"]}}})

    def test_deep_setting_with_dict(self):
        ad = AppendingDict()
        ad.a.b.c = 1
        ad.a = {"b": {"d": 2}}
        self.assertDictEqual(ad.to_dict(), {"a": {"b": {"c": ['1'], "d": ['2']}}})

    def test_setting_with_sequence(self):
        ad = AppendingDict()
        ad.a = [1, "b"]
        self.assertDictEqual(ad.to_dict(), {"a": ['1', 'b']})

    def test_setting_existing_key_with_sequence(self):
        ad = AppendingDict()
        ad.a = [1, "b"]
        ad.a = [2, "c"]
        self.assertDictEqual(ad.to_dict(), {"a": ['1', 'b', '2', 'c']})

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
            ad.to_dict(), {"a": {"b": ["3"], "c": {"d": ["4"]}, "e": ["1"]}})

    def test_updating_does_not_work(self):
        """
        Have not yet implemented this
        """
        ad = AppendingDict()
        d = {"a": 1, "b": {"c": 3}}
        self.assertRaises(NotImplementedError, ad.update(d))

    def test_set_string_value(self):
        ad = AppendingDict()
        ad.a = "abc"
        self.assertDictEqual(ad.to_dict(), {"a": ["abc"]})

    def test_to_dict(self):
        orig = {"a": {"b": ["3"], "c": {"d": ["4"]}, "e": ["1"]}}
        ad = AppendingDict(orig)
        d = ad.to_dict()
        self.assertDictEqual(orig, d)
