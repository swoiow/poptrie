import os
import socket
import unittest

import poptrie  # 确保你已经 pip install . 或者安装了 whl

from build_bin import BinBuilder  # 假设 build_bin.py 在同级或已加入路径


class TestPopTrie(unittest.TestCase):
    BIN_PATH = "test_china_ip.bin"
    CN_CODE = (ord("C") << 8) | ord("N")
    US_CODE = (ord("U") << 8) | ord("S")

    @classmethod
    def setUpClass(cls):
        # 构建测试数据集
        builder = BinBuilder()
        cls.test_data = [
            ("1.0.1.0/24", cls.CN_CODE),  # 标准 IPv4
            ("110.16.0.0/12", cls.CN_CODE),  # 跨字节 IPv4
            ("192.168.1.0/24", cls.CN_CODE),  # 用于测试不匹配
            ("240e::/18", cls.CN_CODE),  # 重点测试：非对齐 IPv6
            ("2001:da8::/32", cls.US_CODE),  # 教育网 IPv6
            ("1.0.1.5/32", cls.CN_CODE),  # 重复添加 (测试合并)
            ("240e:0:0:0:0:0:0:1/128", cls.CN_CODE),  # 子网被 240e::/18 覆盖
        ]
        for cidr, code in cls.test_data:
            builder.add_cidr(cidr, code)
        builder.save(cls.BIN_PATH)
        cls.searcher = poptrie.IpSearcher(cls.BIN_PATH)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "searcher"):
            del cls.searcher  # 释放 mmap
        if os.path.exists(cls.BIN_PATH):
            os.remove(cls.BIN_PATH)

    def test_ipv4_basic(self):
        # 命中测试
        self.assertTrue(self.searcher.contains_ip(socket.inet_pton(socket.AF_INET, "1.0.1.1")))
        self.assertTrue(self.searcher.contains_ip(socket.inet_pton(socket.AF_INET, "110.16.255.255")))
        # 未命中测试
        self.assertFalse(self.searcher.contains_ip(socket.inet_pton(socket.AF_INET, "8.8.8.8")))
        self.assertFalse(self.searcher.contains_ip(socket.inet_pton(socket.AF_INET, "192.168.2.1")))

    def test_ipv6_boundary(self):
        # 240e::/18 范围：240e:0000:: 到 240e:3fff:ffff...
        self.assertTrue(self.searcher.contains_ip(socket.inet_pton(socket.AF_INET6, "240e::")))
        self.assertTrue(self.searcher.contains_ip(socket.inet_pton(socket.AF_INET6, "240e::2")))
        self.assertTrue(self.searcher.contains_ip(socket.inet_pton(socket.AF_INET6, "240e:3fff:ffff:ffff::1")))

        # 边界外
        self.assertFalse(self.searcher.contains_ip(socket.inet_pton(socket.AF_INET6, "240e:4000::")))
        self.assertFalse(self.searcher.contains_ip(socket.inet_pton(socket.AF_INET6, "2001:4860:4860::8888")))

    def test_batch_check(self):
        ips = ["1.0.1.1", "8.8.8.8", "240e::1", "2001:db8::"]
        results = self.searcher.contains_strings(ips)
        self.assertEqual(results, [True, False, True, False])

    def test_batch_check_packed(self):
        # 测试 IPv4 批量流
        v4_ips = ["1.0.1.1", "8.8.8.8", "110.16.0.1", "127.0.0.1"]
        packed_v4 = b"".join([socket.inet_pton(socket.AF_INET, ip) for ip in v4_ips])
        results = self.searcher.contains_packed(packed_v4, False)
        self.assertEqual(results, [True, False, True, False])

    def test_country_code(self):
        self.assertEqual(
            self.searcher.lookup_code(socket.inet_pton(socket.AF_INET, "1.0.1.1")),
            self.CN_CODE,
        )
        self.assertEqual(
            self.searcher.lookup_code(socket.inet_pton(socket.AF_INET6, "2001:da8::1")),
            self.US_CODE,
        )
        self.assertEqual(
            self.searcher.lookup_code(socket.inet_pton(socket.AF_INET, "8.8.8.8")),
            0,
        )


if __name__ == "__main__":
    unittest.main()
