from __future__ import annotations

import itertools
import socket
from pathlib import Path
from typing import Iterable, Optional

import poptrie


class IpSearcher:
    """工业化 IP 查询封装，面向调用方的语义化接口。

    :param bin_path: Path to the binary data file.
    :return: None.
    """

    def __init__(self, bin_path: str | Path) -> None:
        """初始化查询器。

        :param bin_path: Path to the binary data file.
        :return: None.
        """
        self._searcher = poptrie.IpSearcher(str(bin_path))
        self._country_map = self._build_country_map()
        self._cn_code = self._country_code_to_u16("CN")

    @staticmethod
    def _build_country_map() -> dict[int, str]:
        """构建 AA..ZZ 的 u16 到国家码映射。

        :return: Mapping from u16 to 2-letter codes.
        """
        mapping: dict[int, str] = {}
        for first, second in itertools.product(
            range(ord("A"), ord("Z") + 1),
            range(ord("A"), ord("Z") + 1),
        ):
            code = (first << 8) | second
            mapping[code] = f"{chr(first)}{chr(second)}"
        return mapping

    @staticmethod
    def _country_code_to_u16(country_code: str) -> int:
        """将 2 位国家码转换为 u16。

        :param country_code: 2-letter country code.
        :return: u16 country code.
        """
        country_code = country_code.upper()
        return (ord(country_code[0]) << 8) | ord(country_code[1])

    def _code_to_country(self, code: int) -> Optional[str]:
        """将国家码（u16）转换为 2 位字符串。

        :param code: Country code (u16).
        :return: Country string, or None when not matched.
        """
        if code == 0:
            return None
        return self._country_map.get(code)

    @staticmethod
    def _normalize_ip(ip_value: str) -> bytes:
        """将 IP 字符串转换为 packed bytes。

        :param ip_value: IP string (IPv4 or IPv6).
        :return: Packed IP bytes.
        """
        try:
            return socket.inet_pton(socket.AF_INET, ip_value)
        except OSError:
            return socket.inet_pton(socket.AF_INET6, ip_value)

    def __contains__(self, ip_value: str) -> bool:
        """支持 `ip in searcher` 语法。

        :param ip_value: IP string (IPv4 or IPv6).
        :return: True if matched, otherwise False.
        """
        return self.contains_ip(ip_value)

    def contains_ip(self, ip: str) -> bool:
        """判断 IP 是否命中数据集。

        :param ip: IP string (IPv4 or IPv6).
        :return: True if matched, otherwise False.
        """
        packed = self._normalize_ip(ip)
        return self._searcher.contains_ip(packed)

    def contains_ips(self, ips: Iterable[str]) -> list[tuple[str, bool]]:
        """批量判断 IP 是否命中数据集。

        :param ips: IP strings (IPv4 or IPv6).
        :return: (ip, matched) tuples aligned to input order.
        """
        ip_list = list(ips)
        results = self._searcher.contains_strings(ip_list)
        return [(ip, matched) for ip, matched in zip(ip_list, results)]

    def contains_ips_fast(self, packed_ips: bytes, is_v6: bool) -> list[tuple[str, bool]]:
        """高性能批量判断 IP 是否命中数据集。

        :param packed_ips: Flat buffer of IP bytes.
        :param is_v6: True when each IP is 16 bytes, False for 4 bytes.
        :return: (ip, matched) tuples aligned to packed order.
        """
        results = self._searcher.contains_packed(packed_ips, is_v6=is_v6)
        stride = 16 if is_v6 else 4
        family = socket.AF_INET6 if is_v6 else socket.AF_INET
        return [
            (
                socket.inet_ntop(family, packed_ips[offset:offset + stride]),
                matched,
            )
            for offset, matched in zip(range(0, len(packed_ips), stride), results)
        ]

    def lookup_country(self, ip: str) -> Optional[str]:
        """查询 IP 对应国家码。

        :param ip: IP string (IPv4 or IPv6).
        :return: Country string, or None when not matched.
        """
        packed = self._normalize_ip(ip)
        code = self._searcher.lookup_code(packed)
        return self._code_to_country(code)

    def lookup_countries(self, ips: Iterable[str]) -> list[tuple[str, Optional[str]]]:
        """批量查询 IP 对应国家码。

        :param ips: IP strings (IPv4 or IPv6).
        :return: (ip, country) tuples aligned to input order.
        """
        ip_list = list(ips)
        codes = self._searcher.lookup_codes_strings(ip_list)
        return [(ip, self._code_to_country(code)) for ip, code in zip(ip_list, codes)]

    def lookup_countries_fast(
        self,
        packed_ips: bytes,
        is_v6: bool,
    ) -> list[tuple[str, Optional[str]]]:
        """高性能批量查询 IP 对应国家码。

        :param packed_ips: Flat buffer of IP bytes.
        :param is_v6: True when each IP is 16 bytes, False for 4 bytes.
        :return: (ip, country) tuples aligned to packed order.
        """
        codes = self._searcher.lookup_codes_packed(packed_ips, is_v6=is_v6)
        stride = 16 if is_v6 else 4
        family = socket.AF_INET6 if is_v6 else socket.AF_INET
        return [
            (
                socket.inet_ntop(family, packed_ips[offset:offset + stride]),
                self._code_to_country(code),
            )
            for offset, code in zip(range(0, len(packed_ips), stride), codes)
        ]

    def is_cn(self, ip: str) -> bool:
        """判断 IP 是否属于中国。

        :param ip: IP string (IPv4 or IPv6).
        :return: True if CN, otherwise False.
        """
        packed = self._normalize_ip(ip)
        return self._searcher.lookup_code(packed) == self._cn_code

    def is_cn_batch(self, ips: Iterable[str]) -> list[tuple[str, bool]]:
        """批量判断 IP 是否属于中国。

        :param ips: IP strings (IPv4 or IPv6).
        :return: (ip, is_cn) tuples aligned to input order.
        """
        ip_list = list(ips)
        codes = self._searcher.lookup_codes_strings(ip_list)
        return [(ip, code == self._cn_code) for ip, code in zip(ip_list, codes)]

    def is_cn_fast(self, packed_ips: bytes, is_v6: bool) -> list[tuple[str, bool]]:
        """高性能批量判断 IP 是否属于中国。

        :param packed_ips: Flat buffer of IP bytes.
        :param is_v6: True when each IP is 16 bytes, False for 4 bytes.
        :return: (ip, is_cn) tuples aligned to packed order.
        """
        codes = self._searcher.lookup_codes_packed(packed_ips, is_v6=is_v6)
        stride = 16 if is_v6 else 4
        family = socket.AF_INET6 if is_v6 else socket.AF_INET
        return [
            (
                socket.inet_ntop(family, packed_ips[offset:offset + stride]),
                code == self._cn_code,
            )
            for offset, code in zip(range(0, len(packed_ips), stride), codes)
        ]
