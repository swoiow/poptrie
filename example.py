from __future__ import annotations

import socket
from pathlib import Path

from poptrie.ip_searcher import IpSearcher


def main() -> None:
    bin_path = Path("geo-cn.dat")
    searcher = IpSearcher(bin_path)

    ip = "1.0.1.1"
    print(searcher.contains_ip(ip))
    print(searcher.lookup_country(ip))
    print(searcher.is_cn(ip))

    ips = ["1.0.1.1", "8.8.8.8", "240e::1", "2001:db8::"]
    print(searcher.contains_ips(ips))
    print(searcher.lookup_countries(ips))
    print(searcher.is_cn_batch(ips))

    v4_ips = ["1.0.1.1", "8.8.8.8", "110.16.0.1", "127.0.0.1"]
    packed_v4 = b"".join(socket.inet_pton(socket.AF_INET, ip) for ip in v4_ips)
    print(searcher.contains_ips_fast(packed_v4, is_v6=False))
    print(searcher.lookup_countries_fast(packed_v4, is_v6=False))
    print(searcher.is_cn_fast(packed_v4, is_v6=False))


if __name__ == "__main__":
    main()
