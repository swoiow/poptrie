from __future__ import annotations

import itertools
import socket
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union


class PoptrieError(Exception):
    """Base exception for Poptrie operations."""


def _load_native_ip_searcher():
    from ._native import IpSearcher as NativeIpSearcher

    return NativeIpSearcher


class IpSearcher:
    """Semantic Python facade for the Rust-backed Poptrie searcher."""

    def __init__(self, bin_path: Union[str, Path]) -> None:
        self.path = Path(bin_path)
        if not self.path.exists():
            raise FileNotFoundError(f"Binary file not found: {self.path}")

        try:
            NativeIpSearcher = _load_native_ip_searcher()
            self._searcher = NativeIpSearcher(str(self.path))
        except ImportError as exc:
            raise PoptrieError(f"Failed to import Poptrie native module: {exc}") from exc
        except Exception as exc:
            raise PoptrieError(f"Failed to load Poptrie database: {exc}") from exc

        self._country_map: Optional[Dict[int, str]] = None
        self._china_country_code = self._country_code_to_u16("CN")

    @property
    def country_map(self) -> Dict[int, str]:
        if self._country_map is None:
            self._country_map = self._build_country_map()
        return self._country_map

    @staticmethod
    def _build_country_map() -> Dict[int, str]:
        return {
            (first << 8) | second: f"{chr(first)}{chr(second)}"
            for first, second in itertools.product(range(65, 91), range(65, 91))
        }

    @staticmethod
    def _country_code_to_u16(country_code: str) -> int:
        if len(country_code) != 2:
            return 0
        normalized = country_code.upper()
        return (ord(normalized[0]) << 8) | ord(normalized[1])

    def _country_from_u16(self, country_code: int) -> Optional[str]:
        return self.country_map.get(country_code) if country_code > 0 else None

    @staticmethod
    def _pack_ip(ip: str) -> bytes:
        try:
            return socket.inet_pton(socket.AF_INET, ip)
        except OSError:
            try:
                return socket.inet_pton(socket.AF_INET6, ip)
            except OSError as exc:
                raise ValueError(f"Invalid IP address format: {ip}") from exc

    def __contains__(self, ip: str) -> bool:
        try:
            return self.contains_ip(ip)
        except ValueError:
            return False

    def contains_ip(self, ip: str) -> bool:
        return self._searcher.contains_ip(self._pack_ip(ip))

    def lookup_country(self, ip: str) -> Optional[str]:
        return self._country_from_u16(self._searcher.lookup_country(self._pack_ip(ip)))

    def matches_country(self, ip: str, country_code: str) -> bool:
        return self._searcher.matches_country(
            self._pack_ip(ip), self._country_code_to_u16(country_code)
        )

    def contains_ips(self, ips: Iterable[str]) -> List[bool]:
        return self._searcher.contains_strings(list(ips))

    def lookup_countries(self, ips: Iterable[str]) -> List[Optional[str]]:
        return [
            self._country_from_u16(country_code)
            for country_code in self._searcher.lookup_countries_strings(list(ips))
        ]

    def matches_countries(self, ips: Iterable[str], country_code: str) -> List[bool]:
        return self._searcher.matches_country_strings(
            list(ips), self._country_code_to_u16(country_code)
        )

    def contains_packed(self, packed_ips: bytes, is_v6: bool = False) -> List[bool]:
        return self._searcher.contains_packed(packed_ips, is_v6)

    def lookup_countries_packed(
        self, packed_ips: bytes, is_v6: bool = False,
    ) -> List[Optional[str]]:
        return [
            self._country_from_u16(country_code)
            for country_code in self._searcher.lookup_countries_packed(packed_ips, is_v6)
        ]

    def matches_country_packed(
        self, packed_ips: bytes, country_code: str, is_v6: bool = False,
    ) -> List[bool]:
        return self._searcher.matches_country_packed(
            packed_ips, self._country_code_to_u16(country_code), is_v6
        )

    def is_china(self, ip: str) -> bool:
        return self.matches_country(ip, "CN")
