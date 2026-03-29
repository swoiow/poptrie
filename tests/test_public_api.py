import tempfile
import unittest
from pathlib import Path

from poptrie import IpSearcher

from build_bin import BinBuilder


class TestPublicApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp_dir = tempfile.TemporaryDirectory()
        cls._temp_dir = temp_dir
        cls.bin_path = Path(temp_dir.name) / "public-test.bin"

        builder = BinBuilder()
        builder.add_cidr("1.0.1.0/24")
        builder.add_cidr("240e::/18")
        builder.save(str(cls.bin_path))

        cls.searcher = IpSearcher(cls.bin_path)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "searcher"):
            del cls.searcher
        if hasattr(cls, "_temp_dir"):
            cls._temp_dir.cleanup()

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
        self.assertEqual(self.searcher.lookup_countries(ips), ["CN", None, "CN"])
        self.assertEqual(self.searcher.matches_countries(ips, "CN"), [True, False, True])


if __name__ == "__main__":
    unittest.main()
