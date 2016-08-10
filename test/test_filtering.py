try:
    from unittest2 import TestCase
except ImportError:
    from unittest import TestCase

from dsconfig.filtering import filter_config
from dsconfig.formatting import CLASSES_LEVELS, SERVERS_LEVELS


class FilterTestCase(TestCase):

    def test_filter_json_include_server(self):
        data = {
            "TangoTest": {
                "test": {
                    "TangoTest": {
                        "sys/tg_test/3": {
                            "properties": {
                                "apa": ["4"]
                            },
                        },
                    }
                },
            },
            "OtherServer": {
                "1": {
                    "OtherServer": {
                        "a/b/c": {},
                    }
                }
            }
        }
        filtered = filter_config(data, ["server:TangoTest"],
                                 SERVERS_LEVELS)

        self.assertTrue("TangoTest" in filtered)
        self.assertTrue("OtherServer" not in filtered)
        self.assertEqual(data["TangoTest"], filtered["TangoTest"])

    def test_filter_json_include_class(self):
        data = {
            "TangoTest": {
                "test": {
                    "TangoTest": {
                        "sys/tg_test/3": {
                            "properties": {
                                "apa": ["4"]
                            }
                        }
                    },
                    "IrrelevantClass": {
                        "a/b/c": {}
                    }
                },
                "test2": {
                    "TangoTest": {}
                }

            },

            "OtherServer": {
                "1": {
                    "OtherServer": {
                        "a/b/c": {},
                    }
                }
            }
        }
        filtered = filter_config(data, ["class:TangoTest"], SERVERS_LEVELS)

        self.assertTrue("TangoTest" in filtered)
        self.assertTrue("OtherServer" not in filtered)
        self.assertTrue("test2") in filtered["TangoTest"]
        self.assertTrue("TangoTest" in filtered["TangoTest"]["test"])
        self.assertTrue("IrrelevantClass" not in filtered["TangoTest"]["test"])

    def test_filter_json_include_device(self):
        data = {
            "TangoTest": {
                "test": {
                    "TangoTest": {
                        "sys/tg_test/3": {
                            "properties": {
                                "apa": ["4"]
                            },
                        },
                        "sys/tg_test/4": {
                            "properties": {
                                "bepa": ["5"]
                            }
                        }
                    }
                }
            },
            "OtherServer": {
                "1": {
                    "OtherServer": {
                        "a/b/c": {},
                        "d/e/f": {}
                    }
                }
            }
        }
        expected = {
            "TangoTest": {
                "test": {
                    "TangoTest": {
                        "sys/tg_test/3": {
                            "properties": {
                                "apa": ["4"]
                            }
                        }
                    }
                }
            }
        }
        filtered = filter_config(data, ["device:.*test/3"], SERVERS_LEVELS)
        self.assertEqual(filtered, expected)

    def test_filter_json_include_several(self):
        data = {
            "TangoTest": {
                "test": {
                    "TangoTest": {
                        "sys/tg_test/3": {
                            "properties": {
                                "apa": ["4"]
                            },
                        },
                        "sys/tg_test/4": {
                            "properties": {
                                "bepa": ["5"]
                            }
                        }
                    }
                }
            },
            "OtherServer": {
                "1": {
                    "OtherServer": {
                        "a/b/c": {},
                        "d/a/b": {}
                    }
                }
            }
        }
        expected = {
            "TangoTest": {
                "test": {
                    "TangoTest": {
                        "sys/tg_test/3": {
                            "properties": {
                                "apa": ["4"]
                            }
                        }
                    }
                }
            },
            "OtherServer": {
                "1": {
                    "OtherServer": {
                        "a/b/c": {}
                    }
                }
            }
        }

        filtered = filter_config(data, ["device:.*test/3", "device:^a/"],
                                 SERVERS_LEVELS)
        import json
        print(json.dumps(filtered, indent=4))
        print(json.dumps(expected, indent=4))
        self.assertEqual(filtered, expected)
