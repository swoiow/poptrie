import unittest
from pathlib import Path
from unittest.mock import patch

from poptrie import IpSearcher


class TestPublicApi(unittest.TestCase):
    CN_CODE = (ord("C") << 8) | ord("N")
    US_CODE = (ord("U") << 8) | ord("S")

    @classmethod
    def setUpClass(cls):
        cls.bin_path = Path(__file__)

    @classmethod
    def tearDownClass(cls):
        return None

    def setUp(self):
        self.native_patcher = patch(
            "poptrie.ip_searcher._load_native_ip_searcher",
            return_value=self.native_factory,
        )
        self.native_patcher.start()
        self.native_instance = self._build_native_double()
        self.searcher = IpSearcher(self.bin_path)

    def _build_native_double(self):
        class NativeDouble:
            pass

        native = NativeDouble()
        native.contains_ip = lambda packed_ip: packed_ip in {
            b"\x01\x00\x01\x01",
            b"$\x0e" + b"\x00" * 13 + b"\x01",
        }
        native.lookup_country = (
            lambda packed_ip: self.CN_CODE
            if packed_ip in {b"\x01\x00\x01\x01", b"$\x0e" + b"\x00" * 13 + b"\x01"}
            else 0
        )
        native.matches_country = (
            lambda packed_ip, country_code: native.lookup_country(packed_ip) == country_code
        )
        native.contains_strings = lambda ips: [True, False, True]
        native.lookup_countries_strings = lambda ips: [self.CN_CODE, 0, self.US_CODE]
        native.matches_country_strings = lambda ips, country_code: [True, False, False]
        native.contains_packed = lambda packed_ips, is_v6=False: [True, False]
        native.lookup_countries_packed = lambda packed_ips, is_v6=False: [self.CN_CODE, 0]
        native.matches_country_packed = (
            lambda packed_ips, country_code, is_v6=False: [True, False]
        )
        return native

    def native_factory(self, bin_path):
        self.assertEqual(bin_path, str(self.bin_path))
        return self.native_instance

    def tearDown(self):
        self.native_patcher.stop()

    def test_top_level_facade_module(self):
        self.assertEqual(IpSearcher.__module__, "poptrie.ip_searcher")

    def test_facade_contains_ip(self):
        self.assertTrue(self.searcher.contains_ip("1.0.1.1"))
        self.assertTrue(self.searcher.contains_ip("240e::1"))
        self.assertFalse(self.searcher.contains_ip("8.8.8.8"))

    def test_facade_lookup_country(self):
        self.assertEqual(self.searcher.lookup_country("1.0.1.1"), "CN")
        self.assertEqual(self.searcher.lookup_country("240e::1"), "CN")
        self.assertIsNone(self.searcher.lookup_country("8.8.8.8"))

    def test_facade_country_matching(self):
        self.assertTrue(self.searcher.matches_country("1.0.1.1", "CN"))
        self.assertTrue(self.searcher.is_china("240e::1"))
        self.assertFalse(self.searcher.matches_country("8.8.8.8", "CN"))

    def test_facade_batch_contains(self):
        ips = ["1.0.1.1", "8.8.8.8", "240e::1"]
        self.assertEqual(self.searcher.contains_ips(ips), [True, False, True])

    def test_facade_batch_lookup_countries(self):
        ips = ["1.0.1.1", "8.8.8.8", "240e::1"]
        self.assertEqual(self.searcher.lookup_countries(ips), ["CN", None, "US"])
        self.assertEqual(self.searcher.matches_countries(ips, "CN"), [True, False, False])


if __name__ == "__main__":
    unittest.main()
