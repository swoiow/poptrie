import ipaddress
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path

import poptrie

from build_bin import BinBuilder


class TestBuilder(unittest.TestCase):
    def test_build_cn_bin_from_geoip(self):
        url = os.environ.get(
            "POPTRIE_TEST_GEOIP_URL",
            "",
        )
        if not url:
            self.skipTest("POPTRIE_TEST_GEOIP_URL not set")

        with urllib.request.urlopen(url) as response:
            content = response.read().decode("utf-8")
        cidrs = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        self.assertTrue(cidrs)

        builder = BinBuilder()
        for cidr in cidrs:
            builder.add_cidr(cidr)

        with tempfile.TemporaryDirectory() as temp_dir:
            bin_path = Path(temp_dir) / "cn.bin"
            builder.save(str(bin_path))

            searcher = poptrie.IpSearcher(str(bin_path))
            first_cidr = cidrs[0]
            network = ipaddress.ip_network(first_cidr, strict=False)
            target_ip = network.network_address
            if network.num_addresses > 1:
                target_ip = network.network_address + 1
            matched = searcher.contains_strings([str(target_ip)])[0]
            self.assertTrue(matched)


if __name__ == "__main__":
    unittest.main()
