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

    def test_facade_lookup(self):
        self.assertTrue(self.searcher.lookup("1.0.1.1"))
        self.assertTrue(self.searcher.lookup("240e::1"))
        self.assertFalse(self.searcher.lookup("8.8.8.8"))

    def test_facade_batch_lookup(self):
        ips = ["1.0.1.1", "8.8.8.8", "240e::1"]
        self.assertEqual(self.searcher.batch_lookup(ips), [True, False, True])


if __name__ == "__main__":
    unittest.main()
