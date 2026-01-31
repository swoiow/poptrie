from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

import poptrie


BIN_PATH = Path("china_ip.bin")


def ensure_bin(path: Path) -> None:
    """Ensure the bin file exists by running build_bin.py when missing.

    :param path: Path to the bin file.
    :return: None.
    """
    if path.exists():
        return
    subprocess.run([sys.executable, "build_bin.py"], check=True)


def main() -> None:
    """Run a few examples for the Rust-backed searcher.

    :return: None.
    """
    ensure_bin(BIN_PATH)
    searcher = poptrie.IpSearcher(str(BIN_PATH))

    ip_str = "1.0.1.1"
    ip_bytes = socket.inet_pton(socket.AF_INET, ip_str)
    print(f"{ip_str} -> {searcher.is_china_ip(ip_bytes)}")

    ips = ["1.0.1.1", "8.8.8.8", "240e::1", "2001:db8::"]
    results = searcher.batch_check_strings(ips)
    for ip, matched in zip(ips, results):
        print(f"{ip} -> {matched}")

    v4_ips = ["1.0.1.1", "8.8.8.8", "110.16.0.1", "127.0.0.1"]
    packed_v4 = b"".join(socket.inet_pton(socket.AF_INET, ip) for ip in v4_ips)
    packed_results = searcher.batch_check_packed(packed_v4, is_v6=False)
    for ip, matched in zip(v4_ips, packed_results):
        print(f"{ip} -> {matched}")


if __name__ == "__main__":
    main()
