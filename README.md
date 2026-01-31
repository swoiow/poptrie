# poptrie

Fast IP membership lookup backed by a Rust implementation and exposed to Python via PyO3.

Chinese version: [`README-CN.md`](./README-CN.md).

## Requirements

- Python 3.8+
- Rust toolchain
- `maturin`

## Build and Install

Create a virtual environment and install the module in dev mode:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip maturin
maturin develop --release
```

Build wheels:

```bash
maturin build --release --out dist
```

## Build the Binary Data

The searcher reads a binary file produced by `build_bin.py`.

```bash
python build_bin.py
```

If you change the builder logic, rebuild the bin file to match the 72-byte node alignment.

## Python Usage

```python
import socket
from pathlib import Path

import poptrie


bin_path = Path("china_ip.bin")
searcher = poptrie.IpSearcher(str(bin_path))

ip_bytes = socket.inet_pton(socket.AF_INET, "1.0.1.1")
print(searcher.is_china_ip(ip_bytes))

ips = ["1.0.1.1", "8.8.8.8", "240e::1", "2001:db8::"]
print(searcher.batch_check_strings(ips))

v4_ips = ["1.0.1.1", "8.8.8.8", "110.16.0.1", "127.0.0.1"]
packed_v4 = b"".join(socket.inet_pton(socket.AF_INET, ip) for ip in v4_ips)
print(searcher.batch_check_packed(packed_v4, is_v6=False))
```

## Python Helper Class

If you want a lightweight Python-facing wrapper with docstrings, you can use this class:

```python
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import poptrie


class IpSearcher:
    """Poptrie IP lookup wrapper backed by Rust.

    :param bin_path: Path to the binary data file.
    """

    def __init__(self, bin_path: str | Path) -> None:
        self._searcher = poptrie.IpSearcher(str(bin_path))

    def is_china_ip(self, ip_bytes: bytes) -> bool:
        """Check a single IPv4/IPv6 address in packed bytes.

        :param ip_bytes: 4-byte IPv4 or 16-byte IPv6.
        :return: True if matched, otherwise False.
        """
        return self._searcher.is_china_ip(ip_bytes)

    def batch_check_strings(self, ips: Iterable[str]) -> list[bool]:
        """Check a list of IP strings, preserving input order.

        :param ips: IP strings (IPv4 or IPv6).
        :return: Match results aligned to input order.
        """
        return self._searcher.batch_check_strings(list(ips))

    def batch_check_packed(self, packed_ips: bytes, is_v6: bool) -> list[bool]:
        """Check a packed byte buffer containing IPv4 or IPv6 addresses.

        :param packed_ips: Flat buffer of IP bytes.
        :param is_v6: True when each IP is 16 bytes, False for 4 bytes.
        :return: Match results aligned to the packed order.
        """
        return self._searcher.batch_check_packed(packed_ips, is_v6=is_v6)
```

## API Notes

- `is_china_ip` accepts IPv4/IPv6 bytes (`len == 4` or `len == 16`).
- `batch_check_strings` keeps input order and parses strings in Rust.
- `batch_check_packed` expects a flat byte buffer with a fixed stride of 4 or 16.

## Tests

```bash
python -m unittest discover tests
```

## Example

Run the included example:

```bash
python example.py
python example_production.py
```
