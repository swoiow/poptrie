from __future__ import annotations

import socket
from pathlib import Path
from typing import Iterable

import poptrie


class IpSearcher:
    """Poptrie IP lookup wrapper backed by Rust.
    基于 Rust 的 Poptrie IP 查询封装。

    :param bin_path: Path to the binary data file.
    :return: None.
    """

    def __init__(self, bin_path: str | Path) -> None:
        """Initialize the searcher with a bin path.
        使用 bin 路径初始化查询器。

        :param bin_path: Path to the binary data file.
        :return: None.
        """
        self._searcher = poptrie.IpSearcher(str(bin_path))

    def is_china_ip(self, ip_bytes: bytes) -> bool:
        """Check a single IPv4/IPv6 address in packed bytes.
        查询单个 IP（IPv4/IPv6）对应的 bytes。

        :param ip_bytes: 4-byte IPv4 or 16-byte IPv6.
        :return: True if matched, otherwise False.
        """
        return self._searcher.is_china_ip(ip_bytes)

    def batch_check_strings(self, ips: Iterable[str]) -> list[bool]:
        """Check a list of IP strings, preserving input order.
        批量检查 IP 字符串，保持输入顺序。

        :param ips: IP strings (IPv4 or IPv6).
        :return: Match results aligned to input order.
        """
        return self._searcher.batch_check_strings(list(ips))

    def batch_check_packed(self, packed_ips: bytes, is_v6: bool) -> list[bool]:
        """Check a packed byte buffer containing IPv4 or IPv6 addresses.
        批量检查扁平化字节流的 IP 地址。

        :param packed_ips: Flat buffer of IP bytes.
        :param is_v6: True when each IP is 16 bytes, False for 4 bytes.
        :return: Match results aligned to the packed order.
        """
        return self._searcher.batch_check_packed(packed_ips, is_v6=is_v6)

    def check_ip(self, ip: str) -> bool:
        """Check a single IP string.
        查询单个 IP 字符串。

        :param ip: IP string (IPv4 or IPv6).
        :return: True if matched, otherwise False.
        """
        return self.batch_check_strings([ip])[0]

    def check_ips(self, ips: Iterable[str]) -> list[bool]:
        """Check multiple IP strings, preserving input order.
        批量检查 IP 字符串并保持输入顺序。

        :param ips: IP strings (IPv4 or IPv6).
        :return: Match results aligned to input order.
        """
        return self.batch_check_strings(list(ips))

    def check_packed(self, packed_ips: bytes, is_v6: bool) -> list[bool]:
        """Check a packed byte buffer (alias of batch_check_packed).
        批量检查扁平化字节流（batch_check_packed 的语义化别名）。

        :param packed_ips: Flat buffer of IP bytes.
        :param is_v6: True when each IP is 16 bytes, False for 4 bytes.
        :return: Match results aligned to the packed order.
        """
        return self.batch_check_packed(packed_ips, is_v6=is_v6)

    def batch_check(self, ips: Iterable[str]) -> list[bool]:
        """Auto-split IPv4/IPv6 and keep input order.
        自动分流 IPv4/IPv6，并保持输入顺序。

        :param ips: IP strings (IPv4 or IPv6).
        :return: Match results aligned to input order.
        """
        ip_list = list(ips)
        if not ip_list:
            return []

        v4_indices: list[int] = []
        v6_indices: list[int] = []
        v4_bytes_parts: list[bytes] = []
        v6_bytes_parts: list[bytes] = []

        for index, ip in enumerate(ip_list):
            if ":" in ip:
                v6_indices.append(index)
                v6_bytes_parts.append(socket.inet_pton(socket.AF_INET6, ip))
            else:
                v4_indices.append(index)
                v4_bytes_parts.append(socket.inet_pton(socket.AF_INET, ip))

        results = [False] * len(ip_list)

        if v4_bytes_parts:
            v4_data = b"".join(v4_bytes_parts)
            v4_results = self.batch_check_packed(v4_data, is_v6=False)
            for index, matched in zip(v4_indices, v4_results):
                results[index] = matched

        if v6_bytes_parts:
            v6_data = b"".join(v6_bytes_parts)
            v6_results = self.batch_check_packed(v6_data, is_v6=True)
            for index, matched in zip(v6_indices, v6_results):
                results[index] = matched

        return results


def main() -> None:
    """Run a simple usage demo.
    运行一个简单的用法示例。

    :return: None.
    """
    bin_path = Path("china_ip.bin")
    searcher = IpSearcher(bin_path)

    ip_bytes = socket.inet_pton(socket.AF_INET, "1.0.1.1")
    print(searcher.is_china_ip(ip_bytes))

    ips = ["1.0.1.1", "8.8.8.8", "240e::1", "2001:db8::"]
    print(searcher.check_ips(ips))

    v4_ips = ["1.0.1.1", "8.8.8.8", "110.16.0.1", "127.0.0.1"]
    packed_v4 = b"".join(socket.inet_pton(socket.AF_INET, ip) for ip in v4_ips)
    print(searcher.check_packed(packed_v4, is_v6=False))


if __name__ == "__main__":
    main()
