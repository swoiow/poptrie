from __future__ import annotations

import socket
from pathlib import Path

from poptrie import IpSearcher


def main() -> None:
    bin_path = Path("geo-cn.dat")
    searcher = IpSearcher(bin_path)

    ip = "1.0.1.1"
    print(searcher.lookup(ip))
    print(searcher.get_country(ip))
    print(searcher.is_china(ip))

    ips = ["1.0.1.1", "8.8.8.8", "240e::1", "2001:db8::"]
    print(searcher.batch_lookup(ips))
    print(searcher.batch_get_countries(ips))
    print([country == "CN" for country in searcher.batch_get_countries(ips)])

    v4_ips = ["1.0.1.1", "8.8.8.8", "110.16.0.1", "127.0.0.1"]
    packed_v4 = b"".join(socket.inet_pton(socket.AF_INET, ip) for ip in v4_ips)
    print(searcher.lookup_fast(packed_v4, is_v6=False))
    print(searcher.get_countries_fast(packed_v4, is_v6=False))
    print([country == "CN" for country in searcher.get_countries_fast(packed_v4, is_v6=False)])


if __name__ == "__main__":
    main()
